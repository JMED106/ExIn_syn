"""
    SimuGUI - Graphical Tool to manage simulations..
    Copyright (C) 2017  Jose M. Esnaola-Acebes

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os, time
import multiprocessing
import logging

try:
    import gi
except ImportError:
    logging.exception("Requires pygobject to be installed.")
    gi = None
    exit(1)

try:
    gi.require_version("Gtk", "3.0")
except ValueError:
    logging.exception("Requires gtk3 development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")

try:
    gi.require_version("Gdk", "3.0")
except ValueError:
    logging.exception("Requires gdk development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")

try:
    gi.require_version("GObject", "2.0")
except ValueError:
    logging.exception("Requires GObject development files to be installed.")
except AttributeError:
    logging.exception("pygobject version too old.")
try:
    from gi.repository import Gtk, GObject
except (ImportError, RuntimeError):
    logging.exception("Requires pygobject to be installed.")

import numpy as np
import matplotlib

matplotlib.use("Gtk3Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar

logging.getLogger('gui').addHandler(logging.NullHandler())
TARGET_TYPE_URI_LIST = 0


class MainGui:
    """ Main window which will host a simulation (can be extended to host more), and will
        call to other Widgets such as plots.
    """

    def __init__(self, data, simulation):
        """ A set of data, appropriately formatted is needed, and a callable object
        """

        self.data = data
        self.sfunc = simulation

        self.logger = logging.getLogger('gui.MainGui')
        scriptpath = os.path.realpath(__file__)
        scriptdir = os.path.dirname(scriptpath)

        # GUI interface is loaded from a Glade file
        self.builder = Gtk.Builder()
        self.builder.add_from_file("%s/simu_win_1.0.glade" % scriptdir)

        # We identify windows
        self.window = self.builder.get_object("window1")
        self.window.connect("delete-event", Gtk.main_quit)

        signals = {"gtk_main_quit": Gtk.main_quit,
                   "on_Update_clicked": self.dummy,
                   "on_Pause_clicked": self._on_pause_clicked,
                   "on_Stop_clicked": self._on_stop_clicked,
                   "on_Quit_clicked": self._on_exit_clicked,
                   "on_entry_activate": self._on_value_changed,
                   "on_combo_changed": self._on_combo_changed,
                   "on_add_clicked": self._on_add_clicked,
                   "on_value_changed": self._on_value_changed,
                   "on_menu_new_activate": self.newsimulation,
                   "on_menu_save_activate": self.dummy,
                   "on_menu_open_activate": self.dummy,
                   "on_menu_quit_activate": self._on_exit_clicked,
                   "on_menu_newplot_activate": self.newplot,
                   }

        self.builder.connect_signals(signals)
        self._space = ""

        # Create the list of the combobox with the parameters in data
        combo = self.find_widget_down(self.window, "GtkComboBoxText")  # Find the combobox
        self.listbox = self.find_widget_down(self.window, "GtkListBox")  # FInd the listbox
        self.elements = self.extract_tags(self.data.prmts)  # Create the list
        store = self.update_tag_list(self.elements)  # Create the store
        self.update_combobox(combo, store)  # Update the combobox

        # Prepare multiprocessing framework, we need an input queue and an output queue
        self.q_in = multiprocessing.Queue()
        self.q_out = multiprocessing.Queue()
        self.multi_var = {}  # An additional object of shared memory, for plotting, saving, etc.
        for var in self.data.vars.keys():
            if isinstance(self.data.vars[var], type(np.array([0]))):
                self.multi_var[var] = multiprocessing.Array('f', self.data.vars[var])
            elif isinstance(self.data.vars[var], int):
                self.multi_var[var] = multiprocessing.Value('i', self.data.vars[var])

        self.simu_thread = None
        self.graphs = []

    def _explore_tree(self, widget):
        """ Function to completely explore the widgets of the GUI"""
        self._space += "-"
        for child in widget.get_children():
            self.logger.debug("%s>  %s" % (self._space, child.get_name()))
            try:
                self._explore_tree(child)
            except AttributeError:
                self._space = self._space[:-1]
        self._space = self._space[:-1]

    @staticmethod
    def find_widget_down(source, target):
        """ Method to find a successor child of a given source widget"""
        for child in source.get_children():
            if child.get_name() == target:
                logging.debug("Target child found.")
                return child
            else:
                try:
                    targetchild = MainGui.find_widget_down(child, target)
                    if targetchild:
                        return targetchild
                except AttributeError:
                    logging.debug("Target child not found in this branch.")

    @staticmethod
    def find_widget_up(source, target):
        """ Method for finding an ancestor widget from a source widget."""
        parent = source
        while parent.get_name() != target:
            parent = parent.get_parent()
            try:
                parent.get_name()
            except AttributeError:
                logging.warning("Target widget %s not in this branch." % target)
                return None
        return parent

    @staticmethod
    def extract_tags(dictionary, types=(int, float,)):
        """ Method to extract keys from a dictionary provided their value is either a float number or
            an integer number.
        """
        tags = []
        keys = dictionary.keys()
        for key in keys:
            if isinstance(dictionary[key], types) and not isinstance(dictionary[key], bool):
                tags.append(key)
        return tags

    def dummy(self, event):
        pass

    def _on_exit_clicked(self, event):
        """ Event function to quit the programm, it should take care of every opened process."""
        self.logger.debug('Button %s pressed' % event)
        self._on_stop_clicked(None)
        time.sleep(0.1)
        self.q_in.close()
        self.q_out.close()
        if self.simu_thread:
            if self.simu_thread.is_alive():
                self.simu_thread.terminate()
                self.logger.debug('Thread terminated.')
        for graph in self.graphs:
            if graph:
                graph.PLOT = False

        Gtk.main_quit()

    def _on_pause_clicked(self, event):
        self.logger.debug('Button %s pressed' % event)
        self.data.controls['pause'] = not self.data.controls['pause']
        self.q_in.put({'pause': self.data.controls['pause']})

    def _on_stop_clicked(self, event):
        self.logger.debug('Button %s pressed' % event)
        self.q_in.put({'stop': True})

    def _on_combo_changed(self, combo):
        """ Changing the combobox will change the value of the entry at the right side of the combo box.
            Therefore we need to know in which row or box is the selected combo box. """
        self.logger.debug('Element on %s modified' % combo.get_name())
        # Let's get the name of the parameter and its value
        element = combo.get_active_text()
        value = self.data.prmts[element]
        # Let's get the listboxrow where the combo is located
        listboxrow = self.find_widget_up(combo, 'GtkListBoxRow')
        self.logger.debug("The %s is in the %s" % (combo.get_name(), listboxrow.get_name()))

        # The entry/spinbox next to the combobox
        entry = self.find_widget_down(listboxrow, 'GtkSpinButton')
        if entry:
            # Set the value in the entry
            entry.set_value(value)
        else:
            return 1

    def _on_entry_activate(self, entry):
        self.logger.debug('Element on %s modified' % entry.get_name())
        # We must know the value in the combobox next to the entry
        listboxrow = self.find_widget_up(entry, 'GtkListBoxRow')
        self.logger.debug("The %s is in the %s" % (entry.get_name(), listboxrow.get_name()))
        combo = self.find_widget_down(listboxrow, 'GtkComboBoxText')
        if combo:
            element = combo.get_active_text()
        else:
            return 1
        if element:
            tipo = type(self.data.prmts[element])
            self.logger.debug("Type of %s is %s" % (element, tipo))
        else:
            return 1
        # Fucking comma instead of dot
        value = entry.get_text()
        if tipo != str:
            self.data.prmts[element] = tipo(value.replace(',', '.'))
        else:
            self.data.prmts[element] = value

        self.q_in.put({element: value})

    def _on_value_changed(self, spinbox):
        self.logger.debug('Element on %s modified' % spinbox.get_name())
        # We must know the value in the combobox next to the entry
        listboxrow = self.find_widget_up(spinbox, 'GtkListBoxRow')
        self.logger.debug("The %s is in the %s" % (spinbox.get_name(), listboxrow.get_name()))
        combo = self.find_widget_down(listboxrow, 'GtkComboBoxText')
        if combo:
            element = combo.get_active_text()
        else:
            return 1
        value = spinbox.get_value()
        if element:
            self.data.prmts[element] = value
            self.logger.debug("Element %s changed to %s" % (element, str(value)))
            self.q_in.put({element: value})

    def _on_add_clicked(self, button):
        """ Add a new row to be able to modify another parameter"""
        self.logger.debug('Element on %s modified' % button.get_name())
        # We freeze the previous combo box after checking an element is selected
        prev_row = self.listbox.get_children()[-1]
        prev_combo = self.find_widget_down(prev_row, "GtkComboBoxText")
        element = prev_combo.get_active_text()
        if not element:
            self.logger.warning("The previous combo box has not been used yet.")
            return 1
        else:
            # We also remove the previously used element from the new list (to avoid repetition)
            prev_element = prev_combo.get_active_text()
            self.elements.remove(prev_element)
            model = self.update_tag_list(self.elements)

        prev_combo.set_sensitive(False)
        newbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)  # The box containing the widgets
        self.listbox.insert(newbox, -1)  # The new listboxrow

        # First child
        combobox = Gtk.ComboBoxText.new()  # The combobox
        self.update_combobox(combobox, model)
        combobox.connect("changed", self._on_combo_changed)
        newbox.pack_start(combobox, True, True, padding=4)

        # Second child
        adjustment = Gtk.Adjustment(0, -100, 1E8, 0.01, 1, 0)
        value = Gtk.SpinButton(adjustment=adjustment, value=0.00, digits=4, numeric=True, width_chars=8,
                               max_width_chars=8, max_length=8)
        value.set_alignment(1.0)
        value.connect("activate", self._on_value_changed)
        value.connect("value-changed", self._on_value_changed)
        newbox.pack_start(value, True, True, padding=4)

        self.window.show_all()

    def newplot(self, menu):
        """ Function that creates a new Gtk window with canvas where a Matplotlib plot is created.
            For that it uses the class Graph.
            It also asks for the variables to be plotted.
        """

        self.logger.debug('Element on %s modified' % menu.get_name())
        # Ask variables and range
        dialog = PlotDialog(self.data.vars, self.data.lims, parent=self.window)
        dialog.run()
        dialog.hide()
        if dialog.accept:
            title = dialog.plt_vars['y'] + ' vs. ' + dialog.plt_vars['x']
            graph = Graph(self.multi_var, title=title, pvars=(dialog.plt_vars['x'], dialog.plt_vars['y']),
                          store=dialog.store, lims=self.data.lims)
            graph.nsteps = self.data.nsteps
            graph.ax.set_xlim(dialog.lim['x'])
            graph.ax.set_ylim(dialog.lim['y'])
            graph.show_all()
            self.graphs.append(graph)
        dialog.destroy()

    def newsimulation(self, menu):
        """ Function to send a job to the child process. TO BE FIXED Stout problem."""
        self.logger.debug('Element on %s modified' % menu.get_name())
        self.data.controls.update({'stop': False, 'pause': True, 'exit': False})
        if self.simu_thread:
            if self.simu_thread.is_alive():
                self.simu_thread.terminate()
                del self.simu_thread

        self.simu_thread = multiprocessing.Process(None, self.sfunc,
                                                   args=(self.data, self.multi_var, self.q_in, self.q_out))
        self.simu_thread.start()

    @staticmethod
    def update_combobox(combo, elements):
        combo.set_model(elements)
        combo.set_entry_text_column(0)

    @staticmethod
    def update_tag_list(elements, listelements=None):
        if listelements is not None:
            del listelements
        element_store = Gtk.ListStore(str)
        if elements:
            for element in elements:
                element_store.append([element])
        return element_store


class PlotDialog(Gtk.Dialog):
    __gtype_name__ = 'PlotDialog'

    def __new__(cls, pvars, lims, parent=None, xactive=None):
        """This method creates and binds the builder window to class.

        In order for this to work correctly, the class of the main
        window in the Glade UI file must be the same as the name of
        this class."""

        app_path = os.path.dirname(__file__)
        try:
            builder = Gtk.Builder()
            builder.add_from_file(os.path.join(app_path, "plot_dialog.glade"))
        except:
            print "Failed to load XML GUI file plot_dialog.glade"
            return -1
        new_object = builder.get_object('plt_dialog')
        new_object.finish_initializing(builder, pvars, lims, parent, xactive)
        return new_object

    def finish_initializing(self, builder, pvars, lims, parent=None, xactive=None):
        """Treat this as the __init__() method.

        Arguments pass in must be passed from __new__()."""

        # Add any other initialization here
        self.logger = logging.getLogger('gui.PlotDialog')
        self._builder = builder

        signals = {"on_plt_combo_changed": self._on_plt_combo_changed,
                   "on_plt_value_changed": self._on_plt_value_changed,
                   "on_cancel": self._on_cancel,
                   "on_accept": self._on_accept
                   }

        builder.connect_signals(signals)
        self.connect("delete-event", self._on_cancel)

        # Create the list of the combobox of the plotting dialog with the variables in data
        combox = self._builder.get_object("plt_combox")
        comboy = self._builder.get_object("plt_comboy")

        self.plt_vars = {'x': 't'}
        self.lim = {'x': lims['t'] * 1, 'y': [0, 1.0]}
        self._default_limits = lims

        # If the parent is not the main window (to add another plot)
        if isinstance(pvars, Gtk.ListStore):
            self.store = pvars
            target = xactive
            self.set_modal(False)
            self.logger.debug("A liststore passed")
            # combox.set_sensitive(False)
        else:
            var_type = type(pvars['t'])
            self._var_elements = MainGui.extract_tags(pvars, types=(var_type,))
            self.store = MainGui.update_tag_list(self._var_elements)
            target = 't'
        MainGui.update_combobox(combox, self.store)
        MainGui.update_combobox(comboy, self.store)

        # Set default values
        combox.set_active(0)
        i = 0
        while combox.get_active_text() != target:
            i += 1
            combox.set_active(i)
        if i == 0:
            comboy.set_active(1)
        else:
            comboy.set_active(0)

        self._on_plt_combo_changed(combox)
        self._on_plt_combo_changed(comboy)

        # Link to the parent window
        if parent:
            self.logger.debug("Linking the dialog to the parent.")
            self.set_transient_for(parent)

        self.accept = False
        self.logger.debug("Dialog initialized.")

    def _on_plt_combo_changed(self, combo):
        """ Changing the combobox will set the variable tag to pass to the graphing class """
        name = combo.get_name()
        self.logger.debug('Element on %s modified' % name)
        # Let's get the name of the variable
        element = combo.get_active_text()
        # Set the value in the variables to be passed to the graph
        self.plt_vars[name[-1]] = element
        # Set the default range values of that element
        grid = combo.get_parent()
        row = grid.child_get_property(combo, 'top_attach')
        column = grid.child_get_property(combo, 'left_attach')
        min_entry = grid.get_child_at(column + 2, row)
        max_entry = grid.get_child_at(column + 3, row)
        try:
            min_entry.set_value(self._default_limits[element][0])
            max_entry.set_value(self._default_limits[element][1])
        except KeyError:
            min_entry.set_value(0)
            max_entry.set_value(1.0)
        self._on_plt_value_changed(min_entry)
        self._on_plt_value_changed(max_entry)

    def _on_plt_value_changed(self, spinbox):
        name = spinbox.get_name()
        value = spinbox.get_value()
        self.logger.debug('Element on %s modified to %f' % (name, value))
        if name[1:] == 'min':
            self.lim[name[0]][0] = value
        else:
            self.lim[name[0]][1] = value

    def _on_accept(self, event):
        self.hide()
        self.accept = True

    def _on_cancel(self, event):
        self.hide()
        self.accept = False


class Graph(Gtk.Window):
    """ Gtk object containing a canvas plus some other widget, such as a toolbox."""

    def __init__(self, data, title='Matplotlib', size=(800, 500), pvars=('t', 're'), store=None, lims=None):
        """ Initialization requires a memory shared data object (dictionary). And some key values
            representing the variables to be plotted.
        """
        Gtk.Window.__init__(self, title=title)
        self.logger = logging.getLogger('gui.Graph')
        self.window = self
        self.vars = [pvars]
        self.store = store
        self.lims = lims
        self.data = data
        self.nsteps = 0

        self.set_default_size(*size)
        self.boxvertical = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.connect("delete-event", self._destroy)
        self.add(self.boxvertical)

        self.toolbar = Gtk.Toolbar()
        self.context = self.toolbar.get_style_context()
        self.context.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
        self.boxvertical.pack_start(self.toolbar, False, False, 0)

        self.refreshbutton = Gtk.ToolButton(Gtk.STOCK_REFRESH)
        self.toolbar.insert(self.refreshbutton, 0)

        self.refreshbutton.connect("clicked", self.run_dynamically)

        self.addbutton = Gtk.ToolButton(Gtk.STOCK_ADD)
        self.toolbar.insert(self.addbutton, 0)
        self.addbutton.connect("clicked", self._add_variable)

        self.box = Gtk.Box()
        self.boxvertical.pack_start(self.box, True, True, 0)

        # This can be put into a figure or a class ####################
        self.fig = plt.Figure(figsize=(10, 10), dpi=80)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        ###############################################################
        self.box.pack_start(self.canvas, True, True, 0)

        self.toolbar2 = NavigationToolbar(self.canvas, self)
        self.boxvertical.pack_start(self.toolbar2, False, True, 0)

        self.statbar = Gtk.Statusbar()
        self.boxvertical.pack_start(self.statbar, False, True, 0)

        self.fig.canvas.mpl_connect('motion_notify_event', self._updatecursorposition)

        # Figure plotting variables
        self.xdata = np.linspace(0, 2.0, 10)
        self.ydata = self.xdata * 0.0
        self.plots = []
        self.p1, = self.ax.plot(self.xdata, self.ydata, animated=False)
        self.plots.append(self.p1)
        self.ax.grid(True)
        self.ax.set_xlabel(pvars[0], fontsize='20')
        self.ax.set_ylabel(pvars[1], fontsize='20')
        self.fig.canvas.draw()
        self.bg = self.fig.canvas.copy_from_bbox(self.ax.bbox)
        self.PLOT = False

    def _resetplot(self):
        # self.ax.cla()
        # self.ax.set_xlim(0, 10)
        # self.ax.set_ylim(0, 10)
        self.ax.grid(True)

    def _destroy(self, *args):
        self.PLOT = False

    def run_dynamically(self, event):
        self.PLOT = not self.PLOT
        GObject.timeout_add(42, self.plot)

    def plot(self):
        while Gtk.events_pending():
            Gtk.main_iteration()
        self._plotpoints()
        return self.PLOT

    def _plotpoints(self):
        """ It changes the data of both axis taking the information from the shared memory object."""
        for p, var in zip(self.plots, self.vars):
            tstep = self.data['tstep'].value % self.nsteps
            if var[0] == 't' and tstep != 0:
                ydata1 = self.data[var[1]][tstep:]
                ydata2 = self.data[var[1]][0:tstep]
                ydata = np.concatenate((ydata1, ydata2))
            else:
                ydata = self.data[var[1]][::]

            p.set_xdata(self.data[var[0]][::50])
            p.set_ydata(ydata[::50])
        # self.ax.set_ylim([np.min(ydata), np.max(ydata)])
        # self.ax.set_xlim([0, 2.0])
        # self.ax.set_ylim([0, 2.0])
        # self.fig.canvas.restore_region(self.bg)
        # self.resetplot()
        # self.ax.draw_artist(self.p1)
        # self.fig.canvas.blit(self.ax.bbox)
        self.canvas.draw()

    def _updatecursorposition(self, event):
        """When cursor inside plot, get position and print to status-bar"""
        if event.inaxes:
            x = event.xdata
            y = event.ydata
            self.statbar.push(1, ("Coordinates:" + " x= " + str(round(x, 3)) + "  y= " + str(round(y, 3))))

    def _add_variable(self, event):
        self.logger.debug("Selecting another variable to plot.")
        dialog = DialogVar(self, self.store)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            p, = self.ax.plot(self.xdata, self.ydata, animated=False)
            self.plots.append(p)
            self.vars.append([self.vars[0][0], dialog.choice])
        elif response == Gtk.ResponseType.CANCEL:
            pass

        dialog.destroy()
        # dialog = PlotDialog(self.store, self.lims, self.window, self.vars[0][0])
        self.logger.debug("Dialog created. Now running...")
        # dialog.run()
        # dialog.hide()
        # if dialog.accept:
        #     self.ax.set_xlim(dialog.lim['x'])
        #     self.ax.set_ylim(dialog.lim['y'])
        #     p, = self.ax.plot(self.xdata, self.ydata, animated=False)
        #     self.plots.append(p)


class DialogVar(Gtk.Dialog):
    def __init__(self, parent, model):
        Gtk.Dialog.__init__(self, "Select new variable", parent, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.logger = logging.getLogger('gui.DialogVar')
        self.set_default_size(150, 100)

        box = self.get_content_area()
        label = Gtk.Label('New variable:')
        box.pack_start(label, True, True, padding=10)
        self.combo = Gtk.ComboBoxText.new()
        MainGui.update_combobox(self.combo, model)
        self.combo.connect("changed", self._on_plt_combo_changed)
        box.pack_start(self.combo, True, True, padding=10)
        self.show_all()

    def _on_plt_combo_changed(self, combo):
        """ Changing the combobox will set the variable tag to pass to the graphing class """
        name = combo.get_name()
        self.logger.debug('Element on %s modified' % name)
        # Let's get the name of the variable
        element = combo.get_active_text()
        self.choice = element

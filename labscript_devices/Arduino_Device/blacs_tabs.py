# Module for setting the blacs tabs for the general Arduino Device

"""
Defines the blacs tab class and GUI for the "Arduino_Device" device
"""

from blacs.device_base_class import DeviceTab
from blacs.tab_base_classes import define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

import os
import numpy as np
import threading, time
from qtutils import UiLoader
from qtutils.qt import QtWidgets, QtGui, QtCore
import pyqtgraph as pg

class Arduino_Device_Tab(DeviceTab):

#Function that sets the GUI for the device on blacs and prepares any necessary variables, lists, dictionaries, etc. - called on start-up
#This function also creates the initial set-up of/ changes to the GUI and links all buttons, spinboxes, etc. to their apporpriate functions
    def initialise_GUI(self):
         layout = self.get_tab_layout()            #sets layout to blacs tab layout
         
         # Loads GUI for the device from a ui document made in QT Designer (and most likely found in the device folder)
         ui_filepath = os.path.join(
             os.path.dirname(os.path.realpath(__file__)), 'device.ui'     #make sure the string here matches that ui document's name
         )
         self.ui = UiLoader().load(ui_filepath)       #loads filepath and sets as a variable for convenient calling 
         #              (Note: the self.ui preface is used OFTEN in this document)
         
         #Creates a scrollArea widget and adds the device ui inside 
         #      (This allows the ui window to be viewed in a smaller frame while maintaining size policies - very useful)
         scrollArea = QtWidgets.QScrollArea()
         scrollArea.setWidget(self.ui)



         #Below are variables to be used later
         
         self.contin_on = False           #flag for pausing/resuming auto-loop
         
         self.data_check_flag = False           #flag to indicate the need to start a new auto-loop thread
         self.device_toggle = True           #toggle flag for device controls sub-tab
         self.graph_toggle = True           #toggle flag for graph sub-tab
         self.offset_tog = False           #toggle flag for the show/hide offset pushbutton
         self.auto_go = False         #flag for starting / killing auto-loop thread (important for reinitializing)
         
         #lists for storing values for button channels, including those that may be used when graphing
         self.chanCol = []          #stores "channel active" colors for convenient and iterative calling
         self.chanDisCol = []          #stores "channel disabled" colors for convenient and iterative calling
         self.chanHovCol = []          #stores "channel hover" colors for convenient and iterative calling
         
         #Boolean values to toggle elements of the pyqtgraph on or off
         self.value_tog = [True, True, True, True, True]
         self.led_tog = True
         
         #These are to store the last values of variables that can be set on the GUI
         self.led_status = ''
         self.last_value_min = 0
         self.last_value_max = 0
         self.last_offset_value = [0, 0, 0, 0]
         self.set_offset = []
         
         #This variable is used to prevent rapid requests to change the LED status (less than 1 second)
         self.last_toggle_time = 0
         

         #integer variables for graphing
         self.loop_time = 0         #starts a time count for the graph
         self.iter_count = 0          #counts the number of iterations (to keep track of points on the graph)
         self.max_graph_points = 21600          #Sets the maximum points to be saved for graphing per plot (here, 21600 corresponds to 
                                                #    the last 12 hours of data, as the auto update is set to 2 seconds)
         self.plot_data = np.zeros([7, 1])         #creates an array of 7 rows and 1 column with 0s as the entries (for graph plotting)
         self.plot_start = 0                #begins the plotting time at zero
         
         #adds the scrollArea widget (containing the interlock GUI) into the layout
         layout.addWidget(scrollArea)
         self.graph_widget = self.ui.graph_widget  #create the graph widget for the ui and redefine for more convenient calling

         # define the data in the graph widget
         self.title = "Device Value Graph"
         self.plt = self.graph_widget.plotItem        # creates a plot window and item object
         self.plt.showGrid(x = True, y = True)        #displays gridlines to more obviously show the value of datapoints in the plot
         self.plt.setLabel('left', 'Values', units = 'units', color='#ffffff', **{'font-size':'10pt'})     #Note: defining units this way allows for autoscaling
         self.plt.setLabel('bottom', 'Time', units ='sec')   #since time is on the x-axis, the units given (seconds) actually mean something
         self.plt.setTitle(self.title)          #gives the graph a title (defined with the "self.title" variable above)
         
         #Used to create a related graph to be shown in one plot and linked along the x-axis while maintaining a differing y-axis variable
         #     For example, imagine a graph where supplied voltage and temperature at a source may be needed (like a TEC controller)
         self.plt2 = pg.ViewBox()          #create a viewbox to contain the related plot
         self.plt.showAxis('right')           #set its axis on the right of the original plot
         self.plt.scene().addItem(self.plt2)         #add plot 2
         self.plt.getAxis('right').linkToView(self.plt2)       #link the related plot to the right axis
         self.plt2.setXLink(self.plt)         #link the x-axes of the graphs together
         self.plt.setLabel('right', 'LED', units = 'Brightness', color='#a1ff67', **{'font-size':'10pt'})  #the color is defined to distinguish the graph
                                     #the "font-size" controls the size of the axis label text
         
         #Create a reference line to plot for each active channel and define attributes
         self.value_1_ref = self.graph_widget.plot(self.plot_data[6], self.plot_data[0], pen ='r', name ='Value_1') #red is 'r' for the pen (can also use '#ff0000')
         self.value_2_ref = self.graph_widget.plot(self.plot_data[6], self.plot_data[1], pen ='#ffa500', name ='Value_2')   #orange in hexcode
         self.value_3_ref = self.graph_widget.plot(self.plot_data[6], self.plot_data[2], pen ='y', name ='Value_3')    #yellow
         self.value_4_ref = self.graph_widget.plot(self.plot_data[6], self.plot_data[3], pen ='c', name ='Value_4')    #cyan

         self.average_ref = self.graph_widget.plot(self.plot_data[6], self.plot_data[4], pen ='#ff00ff', name ='Avg_Value')     #fushia
         
         self.led_ref = self.plt2
         self.led_ref.addItem(pg.PlotCurveItem(self.plot_data[6], self.plot_data[5], pen ='#a1ff67', name ='LED'))       #light-green
         
         #Adds the channel plots as items in a list for convenient calling
         self.value_ref = [self.value_1_ref, self.value_2_ref, self.value_3_ref, self.value_4_ref, self.average_ref]
         
         #Add the value buttons as items in a list for convenient calling
         self.value_buttons = [self.ui.value_1_button, self.ui.value_2_button, self.ui.value_3_button, self.ui.value_4_button, self.ui.average_button]
         
         #Add the offset spinboxes as items to the list self.adjust for convenient calling
         self.adjust = [self.ui.offset_1_adjust, self.ui.offset_2_adjust, self.ui.offset_3_adjust, self.ui.offset_4_adjust]    

         #Create lists for a general sub-tab function to use (based on the different "boxes" created - here we have 2) 
         #     The "boxes" exist so that we can easily hide or show the contents without explicitly naming every label, button, spinbox, etc.
         #NOTE: The names used here as "self.ui.NAME" come directly from the names defined in the ui document and must be referenced as such to be used properly
         self.sub_tab_button = [self.ui.device_controls,  self.ui.device_graph]        
         self.tab_toggle = [self.device_toggle, self.graph_toggle]
         self.sub_tab = [self.ui.device_controls_box, self.ui.device_graph_box]


      #This section of the initialize GUI connects the appropriate signals for the buttons
         
         #Connect the "clicked" signal to the appropriate function for each respective sub-tab
         self.ui.device_controls.clicked.connect(lambda: self.sub_tab_clicked(0)) #Note: to define only one function for both sub-tabs, a lambda variable is used to pass a value
         self.ui.device_graph.clicked.connect(lambda: self.sub_tab_clicked(1))
         
         
         #Connect the "clicked" signal to the appropriate function for the auto-loop start/stop buttons
         self.ui.start_auto_update.clicked.connect(self.on_auto_up)
         self.ui.stop_auto_update.clicked.connect(self.off_auto_up)
            #  Having ".setEnabled(False)" ensures that a user cannot interact with certain buttons before they are ready for use
            #               (This prevents a backlog of queued worker functions and avoids possible confused states for the device)
         self.ui.start_auto_update.setEnabled(False)          
         self.ui.stop_auto_update.setEnabled(False)

         #Connect the "clicked" signal for the offset show/hide button and offset zero button
         self.ui.offset_toggle.clicked.connect(self.offset_clicked)
         self.ui.offset_zero.clicked.connect(self.offset_zero_clicked)
         self.ui.offset_zero.setEnabled(False)       #disable the offset zero button at start-up
         
         #Connect the "clicked" signal for each respective graph channel monitor button (these will hide or show the data on the graph)
         self.ui.value_1_button.clicked.connect(lambda: self.value_clicked(0))
         self.ui.value_2_button.clicked.connect(lambda: self.value_clicked(1))
         self.ui.value_3_button.clicked.connect(lambda: self.value_clicked(2))
         self.ui.value_4_button.clicked.connect(lambda: self.value_clicked(3))
         self.ui.average_button.clicked.connect(lambda: self.value_clicked(4))
         self.ui.led_button.clicked.connect(self.led_clicked)

         #These "clicked" signals correspond to the buttons that have direct functions on the arduino
         self.ui.default_values.clicked.connect(self.default_clicked)         
         self.ui.led_toggle.clicked.connect(self.toggle_led)
         #Disable the "default_values" button and "led_toggle" button
         self.ui.default_values.setEnabled(False)
         self.ui.led_toggle.setEnabled(False)

        
       #These set the parameters for spinboxes (i.e. the adjustment boxes used to send a particular value like value_max to the arduino)
         self.ui.min_adjust.setRange(-1000,1000)   #Sets the range of the minimum value spinbox
         self.set_min = 0   #Creates a placeholder value for the spinbox and stores in self.set_range_vals
         
         self.ui.max_adjust.setRange(-1000,1000)   #Sets the range of the maximum value spinbox
         self.set_max = 0   #Creates a placeholder value for the spinbox and stores in self.set_range_vals
         
         for ch in range(4):
             self.adjust[ch].setRange(-300.00,300.00)   #Sets the range of the offset value spinbox (really a double spinbox here, since this value is a float)
             self.adjust[ch].setDecimals(2)   #Sets the decimal precision in the double spinbox, here up to 2 decimal places
             self.adjust[ch].setSingleStep(0.1)   #Sets the size of a single step in the spinbox (the default step is 1)
             self.set_offset.append(0)   #Creates a placeholder value for each spinbox and stores in self.set_offset
         
         
         #Connect the "editingFinished" signal to the appropriate function for each respective adjustment spinbox
         self.ui.min_adjust.editingFinished.connect(self.send_value_min)
         self.ui.max_adjust.editingFinished.connect(self.send_value_max)
         for ch in range(4):
             self.adjust[ch].editingFinished.connect(self.send_offset_value)
             
         #Diable the spinboxes to start, as adjustments will be queued by the worker
         self.ui.min_adjust.setEnabled(False)
         self.ui.max_adjust.setEnabled(False)
         for ch in range(4):
             self.adjust[ch].setEnabled(False)
         
         # Sets icons and "tool-tip" for start / stop auto-updating buttons   (the icons are part of the "fugue" library from QtGui.QIcon)
         self.ui.start_auto_update.setIcon(QtGui.QIcon(':/qtutils/fugue/control'))
         self.ui.start_auto_update.setToolTip('Starts Automatic Updating of Values')
         self.ui.stop_auto_update.setIcon(QtGui.QIcon(':/qtutils/fugue/control-stop-square'))
         self.ui.stop_auto_update.setToolTip('Ends Automatic Updating of Values')
         
         #Set icons and "tool-tip" for sub-tab buttons
         self.ui.device_controls.setIcon(QtGui.QIcon(':/qtutils/fugue/toggle-small'))
         self.ui.device_controls.setToolTip('Click to hide')
         self.ui.device_graph.setIcon(QtGui.QIcon(':/qtutils/fugue/toggle-small'))
         self.ui.device_graph.setToolTip('Click to hide')
    

         #Define variables of strings for gradient color background of the buttons (to match blacs style)
         #      The gradients here are for colors red, yellow, and green, respectively. They can be generated in QT Designer
         self.Value_1_Col = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(220, 0, 0, 255), stop:1 rgba(255, 0, 0, 255))"
         self.Value_2_Col = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(220, 139, 0, 255), stop:1 rgba(255, 165, 0, 255))"
         self.Value_3_Col = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(220, 220, 0, 255), stop:1 rgba(255, 255, 0, 255))"
         self.Value_4_Col = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(0, 220, 220, 255), stop:1 rgba(0, 255, 255, 255))"
         
         self.AverageCol = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(220, 0, 220, 255), stop:1 rgba(255, 0, 255, 255))"
         self.LEDTogCol = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(0, 220, 0, 255), stop:1 rgba(0, 255, 0, 255))"
         self.LEDGraphCol = "qlineargradient(spread:pad, x1:0.489, y1:0.00568182, x2:0.489, y2:0.482955, stop:0 rgba(139, 220, 89, 255), stop:1 rgba(161, 255, 103, 255))"
    
         #Adds the channel colors as items in a list for convenient calling (They are such long strings, so this happens in 2 steps)
         self.chanCol = [self.Value_1_Col, self.Value_2_Col, self.Value_3_Col, self.Value_4_Col, self.AverageCol, self.LEDTogCol, self.LEDGraphCol]
         
         #Adds the channel untoggled colors as items in a list for convenient calling (following for red, orange, yellow, cyan, fushia, green)
         self.chanDisCol = ["#8c0000", "#8c5900", "#9a9a00", "#009999", "#8c008c", "#008800", "#588c38"]

         #Adds the channel untoggled hover colors as items in a list for convenient calling  (red, orange, yellow, cyan, fushia, green)
         #    Note: this list is specifically used so that an "off" button will display a different color when the cursors hovers over it, 
         #             a feature which is set in the stylesheet for the button
         self.chanHovCol = ["#aa0000", "#aa6c00", "#b8b800", "#00b7b7", "#aa00aa", "#00a600", "#6baa44"]

         
     #Define attributes of the channel monitor button corresponding to a particular line on the graph
     #NOTE: Everytime setText or setStyleSheet are used, all previous settings are forgetten. This means borders, backgrounds, etc. must be redefined 
     #     everytime they are desired to appear (even when just changing the background color)
         for ch in range(4):
             self.value_buttons[ch].setText("Value "+str(ch+1)+" \n 0.00")       #The buttons will display the actual value of the last point, but for now default to zero
             #The "styleSheet" determines all of the appearance features of a button, including color, border, text color, etc.)
             self.value_buttons[ch].setStyleSheet("background-color : %s;border-style: solid;border-width: 1px;"
                                               "border-color: gray;border-radius: 3px" %(self.chanCol[ch]))
         self.ui.average_button.setText("Average Value \n 0.00")       #set the "average_button" text
         self.ui.average_button.setStyleSheet("background-color : %s;border-style: solid;border-width: 1px;"
                                               "border-color: gray;border-radius: 3px" %(self.chanCol[4]))
         self.ui.led_button.setText("LED Graph \n -")       #set the "led_button" text
         self.ui.led_button.setStyleSheet("background-color : %s;border-style: solid;border-width: 1px;"
                                               "border-color: gray;border-radius: 3px" %(self.chanCol[6])) 
         self.ui.led_toggle.setText("LED_Toggle \n - ")       #set the "led_toggle" text
         self.ui.led_toggle.setStyleSheet("background-color : %s;border-style: solid;border-width: 1px;"
                                               "border-color: gray;border-radius: 3px" %(self.chanDisCol[5]))
         
         #Set the style of the other buttons (In this case, add a border so they are easily seen)
         self.ui.default_values.setStyleSheet("border-style: solid;border-width: 1px;border-color: gray;border-radius: 3px")
         self.ui.offset_toggle.setStyleSheet("border-style: solid;border-width: 1px;border-color: gray;border-radius: 3px")
         self.ui.offset_zero.setStyleSheet("border-style: solid;border-width: 1px;border-color: gray;border-radius: 3px")
         self.ui.start_auto_update.setStyleSheet("border-style: solid;border-width: 1px;border-color: gray;border-radius: 3px")
         self.ui.stop_auto_update.setStyleSheet("border-style: solid;border-width: 1px;border-color: gray;border-radius: 3px")
         
         #This hides the "stop_auto_update" button upon start-up of the ui - widgets in general can be shown and hidden as necessary using .show() and .hide()
         self.ui.stop_auto_update.hide()    
         
         #This hides all of the offset spinboxes and the offset zero upon ui start-up
         for n in range(len(self.adjust)):
             self.adjust[n].hide()
         self.ui.offset_zero.hide()
        
         #This hides a blank widget used for spacing (the widget pushes the other subtabs when the graph is hidden)
         self.ui.push_widg.hide()
         
        
         
        
#Function used by blacs to load the device's workers - automatically called upon start-up
    def initialise_workers(self):
        worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties
        worker_initialisation_kwargs['addr'] = self.BLACS_connection
        self.create_worker(
            'main_worker',
            'labscript_devices.Arduino_Device.blacs_workers.Arduino_Device_Worker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'

        #This is most likely not best practice, but gives a way for the blacs start-up to 
        #       set into motion the auto-loop when the device is first loaded or reinitialized
        self.begin_autoloop()       



  #Creates a function for the plot of the particular data - be it temperatures, voltages, etc.
    def plot(self, time, value):    
        self.graph_widget.plot(time, value)

    

####Functions that take a "clicked" signal and activate the appropriate response

    #This function takes a signal from a sub-tab button and toggles that sub-tab between shown and hidden
    def sub_tab_clicked(self, ID):
        if self.tab_toggle[ID]:
            self.sub_tab[ID].hide()       #hide the particular subtab
            #This reveals an empty widget to push the bottom tab towards the top - it should only be used for the last tab 
            if ID == 1:      #Here ID=1, as there are only 2 subtabs. If there were 4 subtabs, it would be ID=3
                self.ui.push_widg.show()
            self.tab_toggle[ID] = False       #set the boolean toggle value to false now, as the subtab is hidden
            #These update the button icon and tool tip, respectively, to match the stat of the tab
            self.sub_tab_button[ID].setIcon(QtGui.QIcon(':/qtutils/fugue/toggle-small-expand'))
            self.sub_tab_button[ID].setToolTip('Click to show')
        else:
            self.sub_tab[ID].show()       #show the particular subtab
            #This ensures that the empty "push widget" is hidden once the bottom subtab is expanded 
            if ID == 1:
                self.ui.push_widg.hide()
            self.tab_toggle[ID] = True       #set the boolean toggle to true, as the subtab is shown once again
            #These update the button icon and tool tip, respectively, to match the stat of the tab
            self.sub_tab_button[ID].setIcon(QtGui.QIcon(':/qtutils/fugue/toggle-small'))
            self.sub_tab_button[ID].setToolTip('Click to hide')
              

    # Function that toggles the value button and display on the graph (no "@define_state" decorator since the worker is left alone)
    def offset_clicked(self, ch):
        if self.offset_tog:
            self.offset_tog = False           #Since offset_tog was True, toggle it to false
            for n in range(len(self.adjust)):
                self.adjust[n].hide()
            self.ui.offset_zero.hide()    
            self.ui.offset_toggle.setText('Set')
            self.ui.offset_toggle.setToolTip('Click to Show Offset Spinboxes')                                                   
        else:
            self.offset_tog = True      #The offset_tog was not True, so return the offset_tog to True
            if not self.tab_toggle[1]:
                self.sub_tab_clicked(1)
            for n in range(len(self.adjust)):
                self.adjust[n].show()
            self.ui.offset_zero.show()
            self.ui.offset_toggle.setText('Hide')
            self.ui.offset_toggle.setToolTip('Click to Hide Offset Spinboxes')

        
    # Function that toggles the value button and display on the graph (no "@define_state" decorator since the worker is left alone)
    def value_clicked(self, ch):
        if self.value_tog[ch]:
            self.value_tog[ch] = False           #Since value_tog was True, toggle it to false
            self.value_ref[ch].setData([],[])          #set the value_ref data to empty lists (effectively clears it from the graph)
            color = self.chanDisCol[ch]
            colorHov = self.chanHovCol[ch]
            self.value_buttons[ch].setToolTip('Click to Show on Graph')                                                   
        else:
            self.value_tog[ch] = True      #The value_tog was not True, so return the value_tog to True
            self.value_ref[ch].setData(self.plot_data[6, 1:self.iter_count], self.plot_data[ch, 1:self.iter_count])
            color = self.chanCol[ch]
            colorHov = ''         #There is no hover color when a channel is enabled, so pass an empty string
            self.value_buttons[ch].setToolTip('Click to Hide from Graph')
        self.value_buttons[ch].setStyleSheet("""QPushButton{background-color : %s; border-style: solid;
                        border-width: 1px;border-color: gray;border-radius: 3px;}
                        QPushButton::hover {background-color: %s;}""" %(color, colorHov))


    # Function that toggles the output led button and display on the graph (no "@define_state" decorator since the worker is left alone)      
    def led_clicked(self, ch=6):
        if self.led_tog:
            self.led_tog = False
            #Since this is an overlaid graph, we must clear it as shown below
            self.led_ref.clear()
            self.led_ref.addItem(pg.PlotCurveItem([], [], pen = '#a1ff67', name = 'LED'))
            self.led_ref.setGeometry(self.plt.vb.sceneBoundingRect())
            #Set the color and hover color button (when the plot is disabled)
            color = self.chanDisCol[6]
            colorHov = self.chanHovCol[6]
            self.ui.led_button.setToolTip('Click to Show on Graph')                                                   
        else:
            self.led_tog = True
            #These properly add the overlaid graph back to the plot_widget as we expect (and with the correct data)
            self.led_ref.clear()
            self.led_ref.addItem(pg.PlotCurveItem(self.plot_data[6, 1:self.iter_count], self.plot_data[5, 1:self.iter_count], pen = '#a1ff67', name = 'LED'))
            self.led_ref.setGeometry(self.plt.vb.sceneBoundingRect())
            #Set the color for the displayed plot
            color = self.chanCol[6]
            colorHov = ''
            self.ui.led_button.setToolTip('Click to Hide from Graph')
        self.ui.led_button.setStyleSheet("""QPushButton{background-color : %s; border-style: solid;
                        border-width: 1px;border-color: gray;border-radius: 3px;}
                        QPushButton::hover {background-color: %s;}""" %(color, colorHov))


    # Function that checks the led status and appropriately updates the button and status indicator     
    #     Note: This function is seperate from a manual toggle of the led_status that activates the blacs_worker, but it was
    #           included here due to its similarities to the other clicked buttons
    def led_status_check(self, ch=5):
        if self.led_status == 'False':     #Since this variable is passed as a string, we must compare it to the string 'False'
            #Set the button color and tool tip
            color = self.chanDisCol[ch]
            colorHov = self.chanHovCol[ch]
            self.ui.led_toggle.setToolTip('Click to turn LED ON')
            #Create a mode message string to be displayed on the button
            mode_mess = "OFF"
            #Set the led status indicator to show that the LED is OFF
            icon = QtGui.QIcon(':/qtutils/fugue/status-offline')     #selects the icon
          # #This is an example of a different icon choice
          #  icon = QtGui.QIcon(':/qtutils/fugue/light-bulb-small-off')
            pixmap = icon.pixmap(QtCore.QSize(16, 16))
            self.ui.led_status_icon.setPixmap(pixmap)
        else:
            #set the button color and tool tip
            color = self.chanCol[ch]
            colorHov = ''
            self.ui.led_toggle.setToolTip('Click to turn LED OFF')
            #Create a mode message string to show the LED is ON
            mode_mess = "ON"
            #Set the led status indicator to show that the LED is ON
            icon = QtGui.QIcon(':/qtutils/fugue/brightness')     #selects the icon
          # #Like above, this is an example of a different icon choice
          #  icon = QtGui.QIcon(':/qtutils/fugue/light-bulb')
            pixmap = icon.pixmap(QtCore.QSize(16, 16))      #creates the pixelmap
            self.ui.led_status_icon.setPixmap(pixmap)      #sets the ui label as the pixelmap icon
        #Take the color, colorHov, and mode_mess and use them to update the button in the GUI
        self.ui.led_toggle.setStyleSheet("""QPushButton{background-color : %s; border-style: solid;
                        border-width: 1px;border-color: gray;border-radius: 3px;}
                        QPushButton::hover {background-color: %s;}""" %(color, colorHov))
        self.ui.led_toggle.setText("%s \n %s" %('LED_Toggle', mode_mess))
        
                        
    #This takes a signal from default and activates the appropriate function to contact the worker (Note that this must take a "button")
    #Decorator Note: This decorator ensures that there is no attempted use of the worker before "manual" or "transition to manual" mode
    #      It prevents attempted communications with worker functions while shots are being taken
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True) 
    def default_clicked(self, button):
        #Prevent rapid successive button clicks
        self.ui.default_values.setEnabled(False)
        QtCore.QTimer.singleShot(1500, lambda: self.ui.default_values.setDisabled(False))
        
        #Activate the worker to queue the default value command
        self.send_default()
        if not self.contin_on:
            self.grab_default_pack()


    #This takes a signal from offset-zero and activates the appropriate function to contact the worker (note that this must take a "button")
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True) 
    def offset_zero_clicked(self, button):
        #Prevent rapid successive button clicks
        self.ui.offset_zero.setEnabled(False)
        QtCore.QTimer.singleShot(1500, lambda: self.ui.offset_zero.setDisabled(False))
        
        #Set the offset spinboxes to 0
        for n in range(len(self.adjust)):
            self.adjust[n].setValue(0)
        
        #Send the new offset zero values to the worker 
        self.send_offset_value()


####These functions interact directly with the blacs_workers module by queuing work - they must use the "@define_state" decorator
    
    #Function for sending the minimum value to the worker function
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def send_value_min(self):
        print('Sending New Minimum...')
        self.set_min = self.ui.min_adjust.value()           #defines variable self.set_min as the value read from in the min_adjust spinbox
        self.last_value_min = self.set_min        #sets the last value minimum to the setting sent
        if not self.contin_on and self.set_min >= self.last_value_max:
            new_min = self.last_value_max - 1
            self.ui.min_adjust.setValue(new_min)
            self.last_value_min = new_min
        #Note: A check for the new value being the current value must occur in the worker module due to a StopIteration error. It is likely
        #      that this error is a result of using the yield() function
        yield(self.queue_work(self._primary_worker,'set_min_value', self.set_min))       #This is the proper way to queue work from the worker
                                                                                         #Note: The string here is the method name found in the worker class
    
    #Function for sending the minimum value to the worker function
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def send_value_max(self):
        print('Sending New Maximum...')
        self.set_max = self.ui.max_adjust.value()           #defines variable self.set_max as the value read from in the max_adjust spinbox
        self.last_value_max = self.set_max
        if not self.contin_on and self.set_max <= self.last_value_min:
            new_max = self.last_value_min + 1
            self.ui.max_adjust.setValue(new_max)
            self.last_value_max = new_max
        yield(self.queue_work(self._primary_worker,'set_max_value', self.set_max))
        
        
    #Function for sending the minimum value to the worker function
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def send_offset_value(self):
        print('Sending New Offset Value...')
        for ch in range(4):
            set_value = self.adjust[ch].value()
            self.set_offset[ch] = set_value                     #defines variable self.set_offset as the value read from in the offset_adjust spinbox
            self.last_offset_value[ch] = set_value
        yield(self.queue_work(self._primary_worker,'set_offset_value', self.set_offset))
        

    #Function that activates the defaults worker function to reset setpoints to the arduino's default values
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def send_default(self):
        print('Sending Request for Defaults...')
        yield(self.queue_work(self._primary_worker,'set_defaults'))


    #Function that activates the defaults worker function to grab the default values for updating the GUI
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def grab_default_pack(self):
        print('Sending Request for Default Values...')
        self.default_pack = yield(self.queue_work(self._primary_worker,'grab_defaults'))
        self.ui.min_adjust.setValue(float(self.default_pack['Min']))
        self.ui.max_adjust.setValue(float(self.default_pack['Max']))
        for ch in range(len(self.adjust)):
            self.adjust[ch].setValue(float(self.default_pack['Off']))
        

    #Function that requests a change to the LED based on a GUI button interaction
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def toggle_led(self, button=0):          #"button" is included because the led toggle button directly connects here
        #These lines create a cooldown for button presses by disabling the button for a set amount of time (here, 3 seconds) after a click
        self.ui.led_toggle.setEnabled(False)
        QtCore.QTimer.singleShot(3000, lambda: self.ui.led_toggle.setDisabled(False))
        #This if/else sets the button style as appropriate
        if self.led_status == 'False':    
            self.ui.led_toggle.setStyleSheet("""QPushButton{background-color : %s; border-style: solid;
                            border-width: 1px;border-color: gray;border-radius: 3px;}
                            QPushButton::hover {background-color: %s;}""" %(self.chanCol[5], ''))
        else:
            self.ui.led_toggle.setStyleSheet("""QPushButton{background-color : %s; border-style: solid;
                            border-width: 1px;border-color: gray;border-radius: 3px;}
                            QPushButton::hover {background-color: %s;}""" %(self.chanDisCol[5], self.chanHovCol[5]))
        print('Toggling the LED...')
        yield(self.queue_work(self._primary_worker,'switch_led'))       #activates the toggle from the blacs+worker
        self.last_toggle_time = time.time()      #update the last toggle time
        if not self.contin_on:
            if self.led_status == 'True':
                self.led_status = 'False'
            else:
                self.led_status = "True"
            self.led_status_check()



####Functions dealing with auto-looping (will make requests to the blacs_worker without direct user input)

    #This function grabs the initial packet from the arduino (grabs all data values, setpoints for parameters, status readings, etc.)
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def initial_grab(self):
        time.sleep(2)    #necessary to prevent timeout error for automatic reading upon start-up!
        self.full_packet = yield(self.queue_work(self._primary_worker,'initial_packet'))     #use this line to queue the worker to grab a new packet
        
        #Update the led status
        self.led_status = self.full_packet[0]
        #Since labels have no attribute "label.setIcon", create a pixelmap of the desired icon and set pixelmap 
        if self.led_status == "True":
            self.led_val = 1
            icon = QtGui.QIcon(':/qtutils/fugue/brightness')     #selects the icon
            pixmap = icon.pixmap(QtCore.QSize(16, 16))      #creates the pixelmap
            self.ui.led_status_icon.setPixmap(pixmap)      #sets the ui label as the pixelmap icon
        elif self.led_status == "False":
            self.led_val = 0
            icon = QtGui.QIcon(':/qtutils/fugue/status-offline')     #selects the icon
            pixmap = icon.pixmap(QtCore.QSize(16, 16))
            self.ui.led_status_icon.setPixmap(pixmap)
        else:
            self.ui.led_status_icon.setText("%s" %(self.led_status))     #if something else was passed, print the message
            self.led_val = 0.5      #The status is unknown, so make the value on the graph halfway between the two possibilities
        self.ui.led_button.setText("%s \n %d" %('LED Graph', self.led_val))
        
        #Update the important value displayed on its button
        for ch in range(4):
            self.value_buttons[ch].setText("%s \n %.2f" %('Value '+str(ch+1), round(float(self.full_packet[1][str(ch+1)]),2)))
        
        #Update the minimum value spinbox
        if float(self.full_packet[2]) != self.last_value_min:        #This prevents the spinbox from reverting to the current value when being set
            self.ui.min_adjust.setValue(float(self.full_packet[2]))
            self.last_value_min = float(self.full_packet[2])
        
        #Update the maximum value spinbox
        if float(self.full_packet[3]) != self.last_value_max:
            self.ui.max_adjust.setValue(float(self.full_packet[3]))
            self.last_value_max = float(self.full_packet[3])
        #update the offset value spinbox
        for ch in range(4):
            if float(self.full_packet[4][str(ch+1)]) != self.last_offset_value[ch]:
                self.adjust[ch].setValue(float(self.full_packet[4][str(ch+1)]))
                self.last_offset_value[ch] = float(self.full_packet[4][str(ch+1)])
        
        #Update the average_value
        self.ui.average_button.setText("%s \n %.2f" %('Average', round(float(self.full_packet[5]),2)))
            
        #Start the auto-updating loop
        self.on_auto_up()    
        
        
    #Function used by auto-loop to grab a new packet and then update the blacs tab with the appropriate values/ information
    @define_state(MODE_MANUAL|MODE_TRANSITION_TO_MANUAL,True)      
    def grab_packet_update(self):
        print('Attempting to Grab New Packet...')
        self.full_packet = yield(self.queue_work(self._primary_worker,'new_packet', verbose = False)) #grab the new packets from the worker
        
                                                                                              #verbose = False prevents printouts from occurring  
     #Set the buttons and spinboxes with the appropriate updated information
 
        #Update the led status
        self.led_status = self.full_packet[0]
        #Since labels have no attribute "label.setIcon", create a pixelmap of the desired icon and set pixelmap 
        if self.led_status == "True":
            self.led_val = 1
            icon = QtGui.QIcon(':/qtutils/fugue/brightness')     #selects the icon
            pixmap = icon.pixmap(QtCore.QSize(16, 16))      #creates the pixelmap
            self.ui.led_status_icon.setPixmap(pixmap)      #sets the ui label as the pixelmap icon
        elif self.led_status == "False":
            self.led_val = 0
            icon = QtGui.QIcon(':/qtutils/fugue/status-offline')     #selects the icon
            pixmap = icon.pixmap(QtCore.QSize(16, 16))
            self.ui.led_status_icon.setPixmap(pixmap)
        else:
            self.ui.led_status_icon.setText("%s" %(self.led_status))     #if something else was passed  , print the message (this is for diagnostics)
            self.led_val = 0.5    #the status is unknown, so make the value on the graph halfway between the two possibilities
        self.ui.led_button.setText("%s \n %d" %('LED Graph', self.led_val))
        
        #Update the important value displayed on its button
        for ch in range(4):
            self.value_buttons[ch].setText("%s \n %.2f" %('Value '+str(ch+1), round(float(self.full_packet[1][str(ch+1)]),2)))
        
        #Update the minimum value spinbox
        if float(self.full_packet[2]) != self.last_value_min:        #This prevents the spinboxes from reverting to the current value when being set
            self.ui.min_adjust.setValue(float(self.full_packet[2]))
            self.last_value_min = float(self.full_packet[2])
        
        #Update the maximum value spinbox
        if float(self.full_packet[3]) != self.last_value_max:
            self.ui.max_adjust.setValue(float(self.full_packet[3]))
            self.last_value_max = float(self.full_packet[3])

        #Update the offset value spinboxes
        for ch in range(4):
            if float(self.full_packet[4][str(ch+1)]) != self.last_offset_value[ch]:
                self.adjust[ch].setValue(float(self.full_packet[4][str(ch+1)]))
                self.last_offset_value[ch] = float(self.full_packet[4][str(ch+1)])
        
        #Update the previous value
        self.previous_value = float(self.full_packet[5])
        
        #Update the average_value
        self.ui.average_button.setText("%s \n %.2f" %('Average', round(float(self.full_packet[5]),2)))
        
        #Check the led status and update as appropriate using the function above
        self.led_status_check()
        
    #Update the graph with the new data for each channel's line      
        
        #Check for the maximum points on the graph, and if reached, remove the oldest column of data 
        if self.iter_count > (self.max_graph_points):
            self.iter_count = self.max_graph_points
            self.plot_data = np.delete(self.plot_data, [0], axis = 1)
        
        #Add the new values and time to the data array    
        self.plot_data = np.insert(self.plot_data, self.iter_count, [self.full_packet[1]['1'],
                                                                     self.full_packet[1]['2'],
                                                                     self.full_packet[1]['3'],
                                                                     self.full_packet[1]['4'],
                                                                     self.full_packet[5],
                                                                     self.led_val,
                                                                     int(time.time()-self.plot_start)], axis=1)
        
        #For each of these channels: if the button is active, plot the respective graph
        for ch in range(5):
            if self.value_tog[ch]:
                self.value_ref[ch].setData(self.plot_data[6, 1:self.iter_count+1], self.plot_data[ch, 1:self.iter_count+1])
        if self.led_tog:
            #Since this graph is overlaid, it must be added in this way
            self.led_ref.clear()
            self.led_ref.addItem(pg.PlotCurveItem(self.plot_data[6, 1:self.iter_count+1], self.plot_data[5, 1:self.iter_count+1], pen = '#a1ff67', name = 'Average'))
            self.led_ref.setGeometry(self.plt.vb.sceneBoundingRect())
            
       #increase point count by 1
        self.iter_count += 1



    #This function activates the auto-loop (continuos_loop) by either creating a new thread or, if one exists, changing the contin_on flag to True
    @define_state(MODE_MANUAL,True)
    def on_auto_up(self, button=0):
        print('Automatic Acquisition Starting...')  
        self.ui.start_auto_update.hide()          #hide the start button
        self.ui.stop_auto_update.show()          #show the stop button
        self.start_continuous()                 #activate the worker function  
        self.contin_on = True                #set the loop flag to True
        if self.data_check_flag == False:          #This checks that no previous auto-loop has been started
            #Create a thread run the automatic loop
            self.check_thread = threading.Thread(
                target=self.continuous_loop, args=(), daemon=True      #Note: daemon allows the thread to close after blacs closes
                )
            self.check_thread.start()      #start the loop thread
            self.data_check_flag = True        #set this flag true to prevent generating new threads
        else:       #if an auto-loop thread already exists, change this flag to true to resume auto-updating
            self.contin_on = True       
    
    #This function stops (pauses) the auto-loop (continuos_loop) by setting the contin_on flag to False
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL, True)
    def off_auto_up(self, button=0, verbose = False):
        if verbose:
            print('Stopping Automatic Acquisition...')
        self.ui.start_auto_update.show()        #show the start button
        self.ui.stop_auto_update.hide()        #hide the stop button
        self.stop_continuous()           #activate the proper worker for a message that the loop stopped
        self.contin_on = False          #set this flag to false to set the thread to an idle mode (prevent automatic updates)


    #Upon start-up / reinitialization, this function activates the inital_grab function in a thread
    #       Note: This function is called by the initialise_workers function
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL, True)
    def begin_autoloop(self):
        #Create a thread that will activate an initial grab and then stop
        self.first_grab_thread = threading.Thread(target=self.initial_grab, args=(), daemon=True)
        self.first_grab_thread.start()
        
        #Enable all of the buttons that will interact with the blacs_worker now that it has initialized
        self.ui.start_auto_update.setEnabled(True)
        self.ui.stop_auto_update.setEnabled(True)
        self.ui.default_values.setEnabled(True)
        self.ui.min_adjust.setEnabled(True)
        self.ui.max_adjust.setEnabled(True)
        for ch in range(4):
            self.adjust[ch].setEnabled(True)
        self.ui.offset_zero.setEnabled(True)  
        self.ui.led_toggle.setEnabled(True)        
        
    
    #Function that activates the worker to display that the auto-acquisition-loop had begun    
    @define_state(MODE_MANUAL, True)
    def start_continuous(self):
        yield(self.queue_work(self._primary_worker,'start_continuous'))
    
    
    #Function that activates the worker to display that the auto-acquisition-loop had been stopped
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL, True)
    def stop_continuous(self):
        yield(self.queue_work(self._primary_worker,'stop_continuous'))
   
    
   #Defines the loop for auto-aquisition of packets (This loop uses self.grab_packet_update() as long as the appropriate flags are active)
    def continuous_loop(self, auto_go=True, interval = 2):     #Note: The interval sets the time between grabs, in seconds
        self.auto_go = auto_go
        time_go = True
        while self.auto_go:
            if self.contin_on:
                self.grab_packet_update()
                time.sleep(interval)      #This prevents the thread from clogging the queue with packet requests
            elif not self.contin_on and not time_go:
                time.sleep(0.2)      #This sleep is needed to maintain proper functionality when the auto-updating is turned off
            if time_go:
                self.plot_start = time.time()
                time_go = False

 
        
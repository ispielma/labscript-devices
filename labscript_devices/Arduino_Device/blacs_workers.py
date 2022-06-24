# Module for setting the blacs workers for the general Arduino Device

"""
Defines the blacs worker class and functions for the "Arduino_Device" device
"""

import time
import numpy as np
import labscript_utils.h5_lock
import h5py

#from .Arduino_Device import CallError       #This is used only if the optional exception handling functions are used for packet grabbing (see commented-out functions below)
from blacs.tab_base_classes import Worker
import labscript_utils.properties


class Arduino_Device_Worker(Worker):
    #Define init for blacs functionality (this connects to the arduino_device class, set initial variables, etc.). Note it is "init", not "__init__"
    def init(self):
        #Import these here for reinitialization purposes (this is importing the Arduino_Device class from the module Arduino_Device)
        global Arduino_Device
        from .Arduino_Device import Arduino_Device
        
        #This imports zprocess, which is needed to run properly with blacs (for server and locking)
        global zprocess; import zprocess

        #connect to the Arduino_Device class as self.device
        self.device = Arduino_Device(self.addr, termination=self.termination) # the address and termination string are passed into here
        print('Connected to Arduino_Device')      #This displays in the blacs_tab terminal for the device - lets the user know connection occurred smoothly
        
        
        # #Define variables here for later use  
        self.timeTag = 0           #used later for tracking time to complete a shot during transition-to-manual (optional)
        
        #These variables should be directly taken from the items given in the data packet (refer to the Arduino_Device module's packet-grabbing)
        self.led_status = ''         #these empty values should match the expected data type - the led_status will be a string
        self.important_value = {}        
        self.value_min = 0
        self.value_max = 0
        self.offset_value = {}
        self.value_average = 0
        
        # #These are used to keep track of communication failures (only needed if using the optional exception handling packet grabbing)
        #self.failcount = 0
        #self.max_attempts = 2
        
        #These lists are typically useful to store the variables, but you can refer to the expicit definitions (as discussed in 
        #       Arduino_Device) if needed for clarity
        #In the blacs_worker, it can be useful to store both the packet and the individual variables (which is done in this example)
        self.full_pack = []        #used to store the packet of values that will be passed from Arduino_Device
        #NOTE: Python lists can be lists of dictionaries and lists, as used here - this can be confusing though, so only use with caution!
        
        #This dictionary can be useful when choosing the specific attributes desired for storage in the hdf5 file (h5 file)
        self.save_pack = {} 
    
        #This dictionary stores the default values (for use when auto-updating is off)
        self.default_pack = {} 
    
    #Defined for blacs functionality - this function is necessary to shutdown the tab and device properly!
    def shutdown(self):
        self.device.close()   #Uses the close method defined in the Arduino_Device class to disconnect from the arduino 


    #Defined for blacs functionality - when the blacs state is transition-to-buffered mode (before a shot), do the minimal required preparation
    #           for the h5 file (and if necessry, halt any extraneous processes)
    def transition_to_buffered(self, device_name, h5file, front_panel_values, refresh):
        self.h5file = h5file        #define h5 for reference
        self.device_name = 'Arduino_Device'          #device name to be called upon later
        #very quickly add the device to the h5 and then return (we will save data after the shot)
        with h5py.File(h5file, 'r') as hdf5_file:           
            print('\n' + h5file)
            self.device_params = labscript_utils.properties.get(
                hdf5_file, device_name, 'device_properties'
            )
        return {}


    #Defined for blacs functionality - when the blacs state is "transition to manual" mode (after a shot), collect the appropriate
    #           device data for the h5 file and reactivate any important manual mode functionalities that were halted (if any)
    def transition_to_manual(self):
        #Start the timer for how long a save takes during a shot (optional, but provides useful tracking of the device holding the lock)
        self.timeTag = time.time()      #set to current time  (optional)
        print('Downloading value changes...')      #printout for the blacs terminal
        
        #Grab a new packet of the values and flush
        self.full_pack = self.device.grab_new_packet()          #grab a new packet
        self.device.call_plumber()     #call to flush the serial bus
        
        self.update_values()   #update all of the individual variables using the latest full packet (defined below)
        
        #self.save_pack is used for adding the attributes into the h5 later. Right now, choose which values should be recorded for the h5
        self.save_pack['LED_status'] = self.led_status
        for ch in self.important_value:
            chanName = 'channel_'+str(ch)+'_value'
            self.save_pack[chanName] = self.important_value[ch]
        self.save_pack['value_min'] = self.value_min
        self.save_pack['value_max'] = self.value_max
        #Note that some values were not included - any particular values can be added or removed as seen fit, but it makes most sense
        #    to keep important readings and possibly also important settings, while leaving out other less important values. The included values
        #    here are meant to give a variety of samples for saving data
        
        downTime = time.time() - self.timeTag   #calculate how much time was spent getting and setting the packet
        print('Took %s seconds' %(downTime))    #This prints the timing to the terminal


     # Now collect the data in an array
        
        self.timeTag = time.time()       #reuse timeTag (for time it takes to write to h5)
        
        #Create a numpy array to serve as the dataset for latest temperature values and fill
        data = np.empty([4, 1], dtype=float)     #This creates a basic 1x1 data array in form n x m. For more data, the array can be changed.
        for ch in self.important_value:
            data[int(ch)-1,0] = self.important_value[ch]      #the data array should typically includes value reads - such as temperatures, voltages, etc.

        #Now open the h5 file after download, create an Arduino_Device folder, and save attributes/ data
        with h5py.File(self.h5file, 'r+') as hdf_file:
            print('Saving attributes and data...')
            grp = hdf_file['/devices/Arduino_Device']  #directs use of grp to an "Arduino_Device" device folder in the h5 file
            for item in self.save_pack:
                grp.attrs.create(item, self.save_pack[item])  #creates an attribute to go with the dataset array for each item in the "save pack"
                
            grp2 = hdf_file.create_group('/data/Readouts') #directs use of "grp2" to a created "/Readouts" subfolder in "/data" 
                            #      (if recording temperatures, this folder would be /Temps rather than /Readouts)
            dset = grp2.create_dataset(self.device_name, track_order= True, data=data)  #creates a dataset for grp2 (from the array "data")
            for ch in self.important_value:
                chanName = 'channel_'+str(ch)+'_value'
                self.save_pack[chanName] = self.important_value[ch]
                dset.attrs.create(chanName, self.save_pack[chanName])   #add dataset attributes, as pertient, to the saved values taken as data
        
            #These are optional
        downTime2 = time.time() - self.timeTag  #calculate time it takes to open and set the values in the h5
        print('Done!')
        print('Took %s seconds' %(downTime2)) #print the time it took to save to the h5 in the terminal for the device (on blacs)
        
        return True


    #Define for blacs
    def program_manual(self, values):        
        return values


    #Define for blacs to control the device during an abort of a sequence
    def abort(self):
        print('aborting!')
        return True


    #Define for blacs to abort during buffered mode (while taking shots)
    def abort_buffered(self):
        print('abort_buffered: ...')
        return self.abort()


    #Define for blacs to abort during transition to buffered mode (right before taking shots)
    def abort_transition_to_buffered(self):
        print('abort_transition_to_buffered: ...')
        return self.abort()


    #Updates all of the seperately defined values based on the "self.full_pack" values taken from the last shot
    def update_values(self):
        #This order follows the order of the the packet (as passed from Arduino_Device)
        self.led_status = self.full_pack[0]         
        self.important_value = self.full_pack[1]
        self.value_min = self.full_pack[2]
        self.value_max = self.full_pack[3]
        self.offset_value = self.full_pack[4]
        self.value_average = self.full_pack[5]
        return 



####The following functions talk to the arduino (and are typically called by the blacs_tabs module)   
    
    #Grabs an entirely new packet from the arduino for an initial run - the arduino will send all values
    def initial_packet(self):
        self.full_pack = self.device.grab_init()
        print('Grabbed initial value packet')
        self.device.call_plumber()     #to flush the serial
        self.update_values()   #update all of the individual variables using the latest full packet
        return self.full_pack
   
   #Optional 
   # # This is an alternate version of the initial packet function that handles exceptions caused by call errors - It can be used in place of
   # #        the initial_packet function above, if handling of errors is useful for your arduino device
   #  #Grabs an entirely new packet from the arduino (This version has exception handling in cases of poor communication)
   #  def initial_packet(self):
   #      attempts = 0
   #      Success = False
   #      while not Success and attempts < self.max_attempts:   
   #          try:
   #              self.full_pack = self.device.grab_init()
   #              Success = True
   #              if attempts != 0:
   #                  print("Success!")
   #          except CallError as error:
   #              print(error)
   #              self.device.clear()     #flush the bus
   #              attempts += 1
   #              print("Attempting Retry", attempts, "...")
   #              if attempts >= self.max_attempts:
   #                  print("No success after maximum attempts!")
   #                  msg = "Communcation with the arduino has failed upon intial packet grabbing! Check the connection!!"
   #                  raise CallError(msg)
   #                  break
   #      print('Grabbed initial value packet')
   #      self.device.call_plumber()     #to flush the serial
   #      self.update_values()   #updates all of the individual variables using the latest full packet
   #      return self.full_pack
    

    #Requests a packet for any changed values (as compared to the last request) - (note that the worker will still see a new "full" packet, but 
    #       only the changed values will actually be sent from the arduino and updated)
    def new_packet(self, verbose = False):
        if verbose:
            print("Requesting new values...")
        self.full_pack = self.device.grab_new_packet()
        self.device.call_plumber()       #to flush the serial
        self.update_values()      #updates all of the individual variables using the latest full packet
        return self.full_pack

   #Optional
   # # This is an alternate version of the new packet function that handles exceptions caused by call errors - It can be used in place of
   # #        the new_packet function above, if handling of communication errors is useful for your arduino device
   #  #Requests a packet for any changed values (as compared to the last request)
   #  def new_packet(self, verbose = True):
   #      lastPack = self.full_pack
   #      if verbose:
   #          print("Requesting new values...")
   #      attempts = 0
   #      Success = False
   #      while not Success and attempts < self.max_attempts:   
   #          try:
   #              self.full_pack = self.device.grab_new_packet()
   #              Success = True
   #              if attempts != 0:
   #                  print("Success!")
   #          except CallError as error:
   #              print(error)
   #              self.device.clear()     #flush the bus
   #              attempts += 1
   #              print("Attempting Retry", attempts, "...")
   #              if attempts >= self.max_attempts:
   #                  print("No success after maximum attempts! Using previous values.")
   #                  self.failcount += 1
   #                  if self.failcount > 9:
   #                      msg = "Communcation with the arduino has failed "+str(self.failcount)+" times! Check the connection!!"
   #                      raise CallError(msg)
   #                  self.full_pack = lastPack
   #                  break
                
   #      self.device.call_plumber()       #to flush the serial
   #      self.update_values()      #updates all of the individual variables using the latest full packet
   #      return self.full_pack


    #Performs a check of the latest called packet and returns the packet (in cases where the arduino should not be contacted and the last call's values
    #        are desired - like say, right after a shot occurs)
    def packet_return(self):
        print("Calling latest packet...")
        return self.full_pack
    
    
    #Accepts a maximum value, and then sends a write command for a changed maximum value
    def set_max_value(self, write_value_max):
        if write_value_max != float(self.value_max):        #Note: This check occurs in this module to prevent a "StopIteration" error
            self.value_max = str(write_value_max)
            print("Writing new maximum value...")
            self.device.set_value_max(write_value_max)
            self.device.call_plumber()     #to flush the serial
            if write_value_max <= float(self.value_min):       #This is useful when auto-updating is off to ensure the program accurately handles the value
                self.value_max = str(float(self.value_min) + 1)
        else:
            pass
        return


    #Accepts a minimum value, and then sends a write command for a changed minimum value
    def set_min_value(self, write_value_min):
        if write_value_min != float(self.value_min):
            self.value_min = str(write_value_min)
            print("Writing new minimum value...")
            self.device.set_value_min(write_value_min)
            self.device.call_plumber()     #to flush the serial
            if write_value_min >= float(self.value_max):
                self.value_min = str(float(self.value_max) - 1)
        else:
            pass
        return


    #Accepts the offset values, and then sends an offset write command for they changed offset values
    def set_offset_value(self, write_offsets):
        cur_offsets = self.offset_value
        #Writes a new setpoint for a particular channel after verifying that that channel's setpoint has changed value
        for ch in range(4):
            chName = str(ch+1)
            chVal = write_offsets[ch]
            cur_ch_offset = cur_offsets[chName]
            #Checks current setpoints and only writes a new one if there is a change (this saves time/ error potential)
            if chVal != cur_ch_offset:
                self.offset_value[chName] = chVal
                print("Writing new offset value...")
                self.device.set_offset_values(ch+1, chVal)
                self.device.call_plumber()     #to flush the serial
            else:
                pass
        return
    
    
    #Sends a write command to set the device range and offset values back to default
    def set_defaults(self):
        print("Resetting to default values...")
        self.device.set_default_settings()
        self.device.call_plumber()     #to flush the serial


    #Grabs the default values for instance where auto-updating is off, in order to set the GUI
    def grab_defaults(self, verbose=False):
        if verbose:
            print("Grabbing the default values...")
        self.default_pack = self.device.grab_default_values()
        self.device.call_plumber()     #to flush the serial
        return self.default_pack


    #Sends a write command to toggle the LED
    def switch_led(self):
        print("Flipping the LED...")
        self.device.toggle_led()
        self.device.call_plumber()     #to flush the serial
  
    
    
####These final four functions are only here for printouts in the terminal to keep tab operation explicit or provide warnings
    #signifies the acquisition of a new packet
    def continuous_loop(self, verbose = True):
        if verbose:
            print("Acquiring...")
 

    #Prints a continuous acquisition start message in the terminal output
    def start_continuous(self, verbose = True):
        if verbose:
            print("Starting automated acquisition") 


    #Prints a continuous acquisition stop message in the terminal output
    def stop_continuous(self, verbose = True):
        if verbose:
            print("Automated acquisition has been stopped")
 

    #Prints a rapid click warning message
    def rapid_click(self, verbose = True):
        if verbose:
            print("The button was clicked too rapidly! Please slow down")        
 
    
#Module for the generic Arduino_Device 

import pyvisa
import sys
import time

class Arduino_Device:
    """"Class for connecting to the Arduino Device using PyVISA"""
    
    #This is the initialization of the device class - including connectivity and basic definiton of variables
    def __init__(self, addr='ASLR?*::INSTR', 
                 timeout=10, termination='\r\n'):  #the timeout is in seconds
                                                   #the termination character should be standard to arduino's newline - \r\n
        rm = pyvisa.ResourceManager()         #sets the pyvisa resource manager
        devices = rm.list_resources(addr)       #this adds the device address to the pyvisa resource manager list
        assert len(devices), "pyvisa didn't find any connected devices matching " + addr   #for when no devices were found at the address
        self.device = rm.open_resource(devices[0])  #this sets self.device to the device at the given address, which is defined in the labscript connection table
        self.device.timeout = 1000 * timeout      #device.timeout is ineterpretted in milliseconds, so assert our timeout in seconds and set
        self.device.read_termination = termination      #the termination defined above (and possibly given in the connection table) is set for the device
        
        # # The arduino sketch has no IDN command and functions perfectly fine without it, but it could be added
        #       as a standardizing initial component in the future, if necessary
        #       This command is typically used to identify a device upon initial connection, where the device says what it is
        
        #self.idn = self.device.query('*IDN?')  
        
        
        
        #These are standard requests to make over VISA (this short-hands them to be easier for later use)
        self.read = self.device.read            #self.read is used to read bytes from serial (i.e. responses from the arduino) 
        self.write = self.device.write             #self.write is used to write bytes to serial (i.e. make calls to the arduino)
        self.query = self.device.query             #self.query writes to serial and then waits for a response (i.e. all-in-one call-response)
        self.flush = self.device.flush             #self.flush clears the serial to ensure there are no unread bits that may clog the serial and lead to communication failures
        self.clear = self.device.clear             #self.clear can be used to clear the buffer on the PC as well as the IO buffer for the device - takes longer than regular flush
        
        #These are defined for particular data about the Arduino device (i.e. for each item to be read in the packet)
        #This should follow the order of the items defined in your init packet (as part of the arduino sketch)
        self.led_status_packet = ""         #the packet strings are only defined here, and thus left empty
        self.important_values_packet = ""
        self.value_min_packet = ""
        self.value_max_packet = ""
        self.offset_values_packet = ""
        self.value_average_packet = ""
        
        #Empty variables to be used for storing various values/strings of information
        #These empty strings may be unncessary with a list approach, but in other applications explicit definition can add clarity
        self.led_status = ""         #the packet strings are only defined here, and thus left empty
        self.last_led_status = ""          #the "last" strings are used when it is useful to check if a value has changed
        
        self.important_values = ""
        self.last_important_values = ""
        
        self.value_min = ""
        self.last_value_min = ""
        
        self.value_max = ""
        self.last_value_max = ""
        
        self.offset_values = ""
        self.last_offset_values = ""
        
        
        self.value_average = ""
        self.last_value_average = ""
        
        
        #AND / OR
               
        #Add an empty list to store the packet, and another empty list for the last packet received
        #This method can be used in place of the explicit definitions so long as the order of each item in the packet is known
        self.packet = []
        self.last_packet = []
        
        
        
        #create an empty dictionary to be used in cases where packet information should be stored in a dictionary
        #   for example, this is useful when passing channels and associated values, where the channels become the keys of the dictionary
        self.this_dict = {}



####  The following functions are internally referred to by other functions in the Arduino_Device class and thus defined seperately

#It should be noted that these functions are useful for generalized application with arduino call-response, and should be mostly 
#    left as they are
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    #Activates a flush of the serial buffer to prevent inaccurate line-reading
    def call_plumber(self, verbose=False):
         if verbose:     #Note: verbose is used for explicit performance tracking, but will create less print-out clutter when left false
             print('Plumber is here - Time to flush')
         self.device.flush(pyvisa.constants.VI_READ_BUF_DISCARD)
         if verbose:
             print("Flush attempted")


#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    #Converts lists into dictionaries of form [Chan: Value] for convienient reference
    #This function is specifically meant to convert channel names and their associated values into a dictionary    
    def convert_to_dict(self, this_list):       #should pass a list for conversion
        self.this_dict = {}         #make sure the dictionary is empty
        for item in range(len(this_list)):         #take each item in the list, one at a time
            this_string = this_list[item]       #take each item in the list as a string
            name, valRaw = this_string.rsplit(';',1)        #parse the string, as necessary, along ; (here, into a name and value)
            val_str = ""            #create an empty value string
            for m in valRaw:            #convert the valRaw into a value ("if, elif, elif" catches digits, decimal points, and negative signs)
                if m.isdigit():
                    val_str = val_str + m           #if m is a digit, add the digit to the value string 
                elif m=='.':
                    val_str = val_str + m           #if m is a decimal point, add a decimal point to the value string
                elif m=='-':
                    val_str = val_str + m           #if m is a negative sign, add a negative sign to the value string
            val = float(val_str)       #now convert the string that only contains digits and decimal points into a float value
            self.this_dict[name] = val        #add the item to the dictionary, with the name being the key and giving our new value
        return self.this_dict     #return the converted dictionary


#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    #Sends a call number to the arduino to verify that the serial is clear and the arduino is ready for a new command   
    def send_call_num(self, verbose=False):
         if verbose:
             print('Generating call number...')
         
      #Generates a random 4 digit number using time.time() - There are other ways to generate random numbers but this suffices here
         call_num_gen = time.time()
         call_str = str(call_num_gen)[-4:]     #this grabs the last four characters of the string given by time.time()
         
         #This "try, except" catches a value error where an occasionl decimal point sneaks into the call number
         try:     
             call_int = int(call_str)    #try to convert to an interger
         except ValueError:
             print("Error: Call number not int()")   #if string is not an integer (i.e. is a float), just send call number 1000
             call_str = '1000'
             call_int = int(call_str)

         if verbose:
            print('The call number being sent is %s' %(call_str))

        #Now send the call number and read response from the arduino
         expected_read ="Call Number received : "+str(call_int)       #this creates the string we should received from the arduino  
         
         #For handling bad communication: Set values used to handle error conditions
         errmsg = ''
         call_read = None        #No read yet, so the value is none
         retries = 0            #Start at retry 0
         maxRetries = 1         #Set the maximum times a retry occurs (here, the loop will only run once)
         #this gives a way to retry a connection in case of a failure
         while call_read is None and retries < maxRetries:
             try:
                 call_read = self.device.query('@callNum, '+call_str)    #send the command "@callNum, [#]" and wait for a response
             
             #If pyvisa has a VISA IO error (like a timeout or busy VISA), set the error message to reflect this and return an blank call-read
             except pyvisa.VisaIOError as error:
                 call_read = ''
                 errmsg = 'VISA Error: '+ error
                 break
             
             #If another general exception occurs, set as a Network error and possibly try again
             except:
                 call_read = ''
                 errmsg = 'Network Error'
                 pass
                    
             retries += 1

        #If the call did not match the expected, print that a call error occurred and set the error message
         if not call_read == expected_read: 
                 self.call_plumber()    #flush the serial bus
                 print('**!Call Error!**', file=sys.stderr)
                 if not errmsg:
                     errmsg = 'Cannot Rectify Call Number!'
                     
         #print information explaining the error details
         if errmsg:    
                err = 'Call failure (expected, recieved, retries, reason): ({}, {}, {}, {})'.format(
                            expected_read,
                            call_read,
                            retries,
                            errmsg)
                print(err, file=sys.stderr)
                #Raise a Call Error, which is a custom exception class defined after the general "Arduino_Device" class
                raise CallError(time.ctime() + " CALL Error: Something could not be rectified during the last call!!")
         return        
        
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 



#### These functions are specifically used for grabbing packets, and should be tweaked to match the data of your arduino device

    #Grabs the full device packet which contains all useful device data to be used by labscript / blacs
    #This packet gives an inital value of all items so the other packets can only send changed information
    def grab_init(self, all=True):
            """Return full packet of values. """
            
            #Send a call number to ensure the serial is clear and the arduino is ready
            self.send_call_num()
            
            self.device.write('@init,')        #command the initial packet
            time.sleep(1)    #allow time for the packet to be printed to serial
            rawOutput = self.device.read_bytes(250, chunk_size = None, break_on_termchar = True)      #read the characters in serial until a newline is reached
            output = rawOutput.decode('utf-8')    #decode the output from bytes to a string

            #This line involves splitting the packet readout along the "#"s into seperate strings
            #FOR PROPER COMMUNICATION, THE ORDER OF INFORMATION MUST MATCH THE SKETCH and the subpackets split should be 1-to-1, 
            #      except an additional junk packet, which keeps the output from grabbing extra characters at the end of the string
            self.led_status_packet, self.important_values_packet, self.value_min_packet, self.value_max_packet, self.offset_values_packet, self.value_average_packet, junk = output.split('#')
            
            ## The packet version can be used in cases where items are well accounted and the above line gets unreasonably long
            # self.packet = output.split('#')

            #This is a useful conversion since arduino true and false will only be sent as 1 or 0, but there may be reason to explicitly
            #    read true of false - however, a 1 or 0 may work just as well.
            if self.led_status_packet == '1':    
                self.led_status_packet = 'True'
            elif self.led_status_packet == '0':
                self.led_status_packet = 'False'
            else:
                self.led_status_packet = self.led_status_packet

            #The saving of packet info below shows both using a packet list and defining each data item independently - only one is necessary
            #    when the lists are used as is. This example uses a hybrid, but it can be altered to fit needs of a particular device
            #Explicit method     
            self.led_status = self.led_status_packet
            self.last_led_status = self.led_status_packet
            #One List method
            self.packet.append(self.led_status_packet)
            self.last_packet.append(self.led_status_packet)
            
            #Explicit method
            self.important_values_list = self.important_values_packet[:-1].split(",")   #this parses the packet into the 4 channels of values
                                                                                 #Note: "[:-1]" removes the last character of the string, an extra comma 
            self.important_values = self.convert_to_dict(self.important_values_list)      #converts the list into a dictionary, where channel #s are the keys
            self.last_important_values = self.important_values              #sets the last_important_values dictionary 
            #One List method      
            #     (In a situation where the items are already sent as a list, I would recommend the explicit method and omitting this) 
            #     That said, python does support nested dictionaries and lists
            self.important_values_list = self.important_values_packet[:-1].split(",")   #this parses the packet into the channel name-and-value strings
            self.important_values = self.convert_to_dict(self.important_values_list)      #converts the list into a dictionary, where channel names are the keys
            self.packet.append(self.important_values)      #nests the dictionary as part of the "packet" list (would have to use self.packet[1][str(CH#])) to access a ch 
            self.last_packet.append(self.important_values)
            
            #Explicit method
            self.value_min = self.value_min_packet
            self.last_value_min = self.value_min_packet
            #One List method            
            self.packet.append(self.value_min_packet)
            self.last_packet.append(self.value_min_packet)
            
            #Explicit method
            self.value_max = self.value_max_packet
            self.last_value_max = self.value_max_packet
            #One List method            
            self.packet.append(self.value_max_packet)
            self.last_packet.append(self.value_max_packet)
            
            #Explicit method
            self.offset_values_list = self.offset_values_packet[:-1].split(",")   #this parses the packet into the 4 channels of offsets (name and value str)
            self.offset_values = self.convert_to_dict(self.offset_values_list)      #converts the list into a dictionary, where channel # are the keys
            self.last_offset_values = self.offset_values              #sets the last_offset_values dictionary 
            # #One List method      
            #self.offset_values_list = self.offset_values_packet[:-1].split(",")     #generate as above
            #self.offset_values = self.convert_to_dict(self.offset_values_list)     #create a dictionary from the list
            self.packet.append(self.offset_values)      #nests the dictionary as part of the "packet" list
            self.last_packet.append(self.offset_values)
            
            #Explicit method
            self.value_average = self.value_average_packet
            self.last_value_average = self.value_average_packet
            #One List method            
            self.packet.append(self.value_average_packet)
            self.last_packet.append(self.value_average_packet)
           
            
            #Ignore junk! (i.e. anything after the last data section of the packet)
           
            #This gives the new packet back to the calling function (typically in the worker) - (One List method)
            return self.packet     

            ##Likewise, the items can be passed inidividually - but this is can be more tedious - (Explicit method)
            #return self.led_status, self.important_values, self.value_min, self.value_max, self.offset_values, self.value_average

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #Grabs a new packet which contains only changed values
    def grab_new_packet(self, all=True):
            """Return updates to values - still sends a full packet. """
            
            #send a call number to ensure the serial is clear and the arduino is ready
            self.send_call_num()

            self.device.write('@pack,')         #command the changed packet   
            rawOutput = self.device.read_bytes(250, chunk_size = None, break_on_termchar = True)      #read the characters in serial until a newline is reached
            output = rawOutput.decode('utf-8')    #decode the output            

            # Read the packet and split into the appropriate variables
            self.led_status_packet, self.important_values_packet, self.value_min_packet, self.value_max_packet, self.offset_values_packet, self.value_average_packet, junk = output.split('#')

            #Update the led status, if a new one exists
            if self.led_status_packet:
                #Same true/false conversion as above
                if self.led_status_packet == '1':    
                    self.led_status_packet = 'True'
                elif self.led_status_packet == '0':
                    self.led_status_packet = 'False'
                else:
                    self.led_status_packet = self.led_status_packet
                    
                #Explicit method
                self.last_led_status = self.led_status
                self.led_status = self.led_status_packet
                #One List method            
                self.last_packet[0] = self.packet[0]
                self.packet[0] = self.led_status_packet

            #Update the important values, if new ones exist
            if self.important_values_packet:
                self.important_values_list = self.important_values_packet[:-1].split(",")   #parse into changed channels
                self.important_values_temp = self.convert_to_dict(self.important_values_list)  
                #Explicit method
                self.last_important_values = self.important_values         #save the last dictionary before updating
                for ch in self.important_values_temp:
                    self.important_values[ch] = self.important_values_temp[ch]     #only updates changed channels, leaving those unchanged alone
                #One List method      
                #for ch in self.important_values_temp:                  #Still needed for One List method
                #    self.important_values[ch] = self.important_values_temp[ch]     #only updates changed channels, leaving those unchanged alone
                self.last_packet[1] = self.packet[1]
                self.packet[1] = self.important_values
                
            #Update the minimum, if a new one exists
            if self.value_min_packet:
                #Explicit method
                self.last_value_min = self.value_min
                self.value_min = self.value_min_packet
                #One List method            
                self.last_packet[2] = self.packet[2]
                self.packet[2] = self.value_min_packet

            #Update the maximum, if a new one exists
            if self.value_max_packet:
                #Explicit method
                self.last_value_max = self.value_max
                self.value_max = self.value_max
                #One List method            
                self.last_packet[3] = self.packet[3]
                self.packet[3] = self.value_max_packet
            
            #Update the offset values, if new ones exist
            if self.offset_values_packet:
                self.offset_values_list = self.offset_values_packet[:-1].split(",")   #this parses the packet into the 4 channels of values
                                                                                     #Note: "[:-1]" removes the last character of the string, an extra comma 
                self.offset_values_temp = self.convert_to_dict(self.offset_values_list)      #converts the list into a dictionary, where channel # are the keys
                #Explicit method
                self.last_offset_values = self.offset_values
                for ch in self.offset_values_temp:
                    self.offset_values[ch] = self.offset_values_temp[ch]     #only updates changed channels, leaving those consistant alone
                #One List method
                # for ch in self.offset_values_temp:      #Needed if using only One List method
                #     self.offset_values[ch] = self.offset_values_temp[ch]     #only updates changed channels, leaving those consistant alone
                self.last_packet[4] = self.packet[4]
                self.packet[4] = self.offset_values
                
            #Update the value average if a new one exists
            if self.value_average_packet:
                #Explicit method
                self.last_value_average = self.value_average
                self.value_average = self.value_average_packet
                #One List method            
                self.last_packet[5] = self.packet[5]
                self.packet[5] = self.value_average_packet

                
            #Ignore junk! (i.e. anything after the last data section of the packet)
           
            #This gives the new packet back to the calling function (typically in the worker) - (One List method)
            return self.packet     

            ##Likewise the items can be passed inidividually - (Explicit method)
            #return self.led_status, self.important_values, self.value_min, self.value_max, self.offset_values, self.value_average
      
    
  
#### These functions are called directly by the blacs_worker, and should be created for the specific data that must be passed to the worker
#      Make sure the functions included here match your data and commands  -   given below are examples for this generic device sketch
#-----------------------------------------------------------------
    #Send command to set a new maximum value, passed to the function as v
    def set_value_max(self, v, verbose=False):
        self.send_call_num()
        setVal = v
        if verbose:
            print('Sending new maximum value...')
        self.device.write('@valueMax, %s,'%(setVal))
        rawOutput = self.device.read_bytes(75, chunk_size = None, break_on_termchar = True)
        output = rawOutput.decode('utf-8')
        self.save_settings()
        print(output, end='')       #Using end='' because the arduino string will contain its own newline character (this prevents double newlines)

#-----------------------------------------------------------------
    #Send command to set a new minimum value, passed to the function as v
    def set_value_min(self, v, verbose=False):
        self.send_call_num()
        setVal = v
        if verbose:
            print('Sending new minimum value...')
        self.device.write('@valueMin, %s,'%(setVal))
        rawOutput = self.device.read_bytes(75, chunk_size = None, break_on_termchar = True)
        output = rawOutput.decode('utf-8')
        self.save_settings()
        print(output, end='')


#-----------------------------------------------------------------
    #Send command to set a new scaling value, passed to the function as v
    def set_offset_values(self, ch, v, verbose=False):
        self.send_call_num()
        setChan = ch
        setVal = v
        if verbose:
            print('Sending new offset value...')
        self.device.write('@offsetValue, %s, %s,'%(setChan, setVal))
        rawOutput = self.device.read_bytes(75, chunk_size = None, break_on_termchar = True)
        output = rawOutput.decode('utf-8')
        self.save_settings()
        print(output, end='')
      

#-----------------------------------------------------------------
    #Send command for the arduino to return all setpoints to the default values stored in the arduino sketch
    def set_default_settings(self, verbose=False):
        self.send_call_num()
        if verbose:
            print('Requesting default settings...')
        output = self.device.query('@default,')
        print(output)
        self.save_settings()
        
        ##As another option, the following set defaults can be hardcoded here, if desired
        ##      In that case, remove everything after send_call_num() and uncomment the section below
        # self.set_value_max(100)
        # self.call_plumber()
        # self.set_value_min(10)
        # self.call_plumber()
        # for ch in range(4):
        #     self.set_offset_values(ch, 0)
        # self.call_plumber()
        # self.save_settings()


#-----------------------------------------------------------------
    #Send command for the arduino to return all setpoints to the default values stored in the arduino sketch
    def grab_default_values(self, verbose=False):
        self.send_call_num()
        if verbose:
            print('Requesting default values...')
        output = self.device.query('@defaultValues,')

        self.default_min, self.default_max, self.default_offset, junk = output.split('#')
        self.default_pack = [self.default_min, self.default_max, self.default_offset]
        self.default_values = self.convert_to_dict(self.default_pack)
        
        ##The following grabbed defaults should be used when hardcoded in set_default_settings
        # self.default_values['Min'] = 70
        # self.default_values['Max'] = 100
        # self.default_values['Off'] = 0
        
        return self.default_values


#-----------------------------------------------------------------    
    #Send the command to save all current setpoint values (This is used internally in the module; the front end tab has not button to call this)
    def save_settings(self, verbose=False):
        self.send_call_num() 
        if verbose:
             print('Saving seetings to Arduino EEPROM...')
        self.device.write('@SV,')
        return        

#-----------------------------------------------------------------
    #Send command to toggle the state of the led, and print the outcome 
    # NOTE: To avoid confusion between blacs and the device, the packet gives information on the led status. This keeps
    #     python correctly matched to the LED status while auto-updating is enabled on the front end
    def toggle_led(self, verbose=False):
        self.send_call_num()
        if verbose:
            print('Toggling state of led...')
        self.device.write('@status,')
        rawOutput = self.device.read_bytes(75, chunk_size = None, break_on_termchar = True)
        output = rawOutput.decode('utf-8')
        print(output, end ='')

        
#----------------------------------------------------------------- 
    #THIS SHOULD ALWAYS BE INCLUDED - OTHERWISE THE DEVICE PORT WILL BE BUSY ON THE NEXT CONTACT AFTER CLOSING BLACS
    #Meant to be used by BLACS / labscript during shutdown procedures (ensures device is disconnected from serial properly)
    def close(self):
        self.device.close()



#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
    
#This is an exception class meant to be used for circumstances with call errors - if using the call number function, this should be used as well

class CallError(Exception):
        pass



####This is a test script to verify the methods of the above class are working properly. It will only run in this file
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == '__main__':
    #add your real device address here, which can be found by referencing you VISA software's onnection address
    #in the case of using NI_MAX, your VISA address for the device will likely be 'ASRL?::INSTR' where the "?" is the port number of the arduino 
    arduino = Arduino_Device(addr='ASRL16::INSTR', timeout=10)
    Test = input('Choose a Test:\n - "1" : Test packet grabbing\n'
                 ' - "2" : Test setting maximum\n'
                 ' - "3" : Test toggling led\n'
                 ' - "4" : Test setting defaults\n'
                 ' - else : Will exit.\n Enter Choice:')
    if Test == "1":     #Test grab_init() and Grab_new_packet()
        print("Test 1 selected!")
        time.sleep(2)
        initial = arduino.grab_init()
        print(initial)
        for r in range(5):
            packet = arduino.grab_new_packet()
            print(packet)
            time.sleep(4)
            arduino.call_plumber(verbose = False)
    elif Test == "2":     #Test set_maximum()
        print("Test 2 selected!")
        initial = arduino.grab_init()
        print(initial)
        time.sleep(2)
        command = input("Give a maximum value in the format:"
                        "'[VALUE]'\nCommand: ")
        arduino.set_value_max(command, verbose=True)
        for r in range(2):
            time.sleep(2)
            arduino.call_plumber()
            packet = arduino.grab_new_packet()
            print(packet)
    elif Test == "3":     #test toggle_led()
        print("Test 3 selected!")
        initial = arduino.grab_init()
        print(initial)
        time.sleep(2)
        for r in range(4):
            arduino.toggle_led()
            time.sleep(2)
            arduino.call_plumber()
            packet = arduino.grab_new_packet()
            print(packet)
    elif Test == "4":     #Test set_default_settings
        print("Test 4 selected!")
        initial = arduino.grab_init()
        print(initial)
        time.sleep(2)
        command = input("Give a minimum value in the format:"
                        "'[VALUE]'\nCommand: ")
        arduino.set_value_min(command, verbose=True)
        command = input("Give a maximum value in the format:"
                        "'[VALUE]'\nCommand: ")
        arduino.set_value_max(command, verbose=True)
        time.sleep(2)
        arduino.call_plumber()
        packet = arduino.grab_new_packet()
        print(packet)
        arduino.call_plumber()
        time.sleep(2)
        arduino.set_default_settings()
        arduino.call_plumber()
        time.sleep(2)
        packet = arduino.grab_new_packet()
        print(packet)
    else:
        print("No test selected")
    print("That's all for now")
    arduino.close()

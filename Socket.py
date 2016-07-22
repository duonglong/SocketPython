# -*- coding: utf-8 -*-
import time
import struct
import socket
import hashlib
import base64
import sys
from select import select
import re
import logging
from threading import Thread
import signal
import json
from win32com.client import Dispatch
from collections import OrderedDict
import urllib2
import pythoncom
import os

# Constants
MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
TEXT = 0x01
BINARY = 0x02


# WebSocket implementation
class WebSocket(object):
    handshake = (
        "HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
        "Upgrade: WebSocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Accept: %(acceptstring)s\r\n"
        "Server: TestTest\r\n"
        "Access-Control-Allow-Origin: http://localhost\r\n"
        "Access-Control-Allow-Credentials: true\r\n"
        "\r\n"
    )

    # Constructor
    def __init__(self, client, server):
        self.client = client
        self.server = server
        self.handshaken = False
        self.header = ""
        self.data = ""

    # Serve this client
    def feed(self, data):

        # If we haven't handshaken yet
        if not self.handshaken:
            logging.debug("No handshake yet")
            self.header += data
            if self.header.find('\r\n\r\n') != -1:
                parts = self.header.split('\r\n\r\n', 1)
                self.header = parts[0]
                if self.dohandshake(self.header, parts[1]):
                    logging.info("Handshake successful")
                    self.handshaken = True

        # We have handshaken
        else:
            logging.debug("Handshake is complete")
            response = ""
            # Decode the data that we received according to section 5 of RFC6455
            recv = self.decodeCharArray(data)
            message = ""
            try:
                recv_data = json.loads(''.join(recv).strip(), object_pairs_hook=OrderedDict)
                if recv_data:
                    if recv_data['action'] == 'PUSH_F1':
                        response = self.setIEElementByName(recv_data['content'])
                    if recv_data['action'] == 'PUSH_DOCUMENT':
                        path = self.saveTaskDocument(recv_data)
                        if path:
                            command = "%d "+path+" %n "+recv_data['doc']['filename']+" {ENTER}"                            
                            self.selectFile(command)
                        else:
                            logging.debug("Can't save file")
                        self.selectFile()
            except Exception, e:
                logging.error(str(e))
                message = str(e)
                pass
            # Send our reply
            self.sendMessage(message)
        
    def saveTaskDocument(self, data):
        request_headers = {
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding":"gzip, deflate, sdch",
            "Accept-Language":"en-US,en;q=0.8,vi;q=0.6",
            "Cache-Control":"max-age=0",
            "Connection":"keep-alive",
            "Cookie":data['cookie'],
            "DNT":"1",            
            "Upgrade-Insecure-Requests":"1",
            "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36"
        }
        doc = data['doc']        
        fileurl = doc['fileurl']
        path = r"C:\HSS\{0}\{1}".format(doc['customer_id'], doc['app_id'])       
        try:
            request = urllib2.Request(fileurl, headers=request_headers)
            f = urllib2.urlopen(request).read()
            if not os.path.exists(path):
                os.makedirs(path)
            with open(r"{0}\{1}".format(path, doc['filename']),"wb") as local_file:
                local_file.write(f)
            return path
        except urllib2.HTTPError, e:
            logging.error(e.headers)
            logging.error(e.code + e.msg)            
            return False        

    # Select file to upload
    def selectFile(self, command):        
        shell = Dispatch("Shell.Application")
        print 12312
        wscript = Dispatch("WScript.Shell")
        print 12312312222222222222222
        # Focus to upload file window on client        
        wscript.AppActivate("Choose File to Upload")        
        wscript.SendKeys(command)
        for win in SHELL.Windows():
            if win.Name == "Windows Internet Explorer" and win.Document.LocationURL == "http://cfris02.fecredit.com.vn/VPBank/adddoc.jsp":
                print win.Document.Title
                upload_script = win.Document.Script._oleobj_.GetIDsOfNames("UploadClick")
                win.Document.Script._oleobj_.Invoke(upload_script, 0, pythoncom.DISPATCH_METHOD, True)
                break
    
    def setIEElementByName(self, data):                
        values = data['values']        
        title = data['title']
        SHELL = Dispatch("Shell.Application")
        for win in SHELL.Windows():            
            if win.Name == "Windows Internet Explorer":                
                if win.Document.getElementsByTagName("title")[0].innerHTML == title:                    
                    for fieldName in values:                        
                        el = win.Document.getElementsByName(fieldName)
                        if el.length:
                            #Change field's value
                            if 'val' in values[fieldName] and values[fieldName]['val']:
                                el[0].value = values[fieldName]['val']
                                print values[fieldName]['val']
                            #Fire event of field
                            if 'event' in values[fieldName] and values[fieldName]['event']:
                                el[0].FireEvent(values[fieldName]['event'])
                                if values[fieldName]['event'] == 'onclick':
                                    while win.ReadyState != 4:
                                        time.sleep(0.5)
                                if values[fieldName]['event'] == 'onchange':
                                    #Wait for field many2one finish loading
                                    time.sleep(1)
                                    popup = SHELL.Windows().Item(SHELL.Windows().Count-1)                                    
                                    if popup.Document.Title != title:
                                        while popup in SHELL.Windows():
                                            time.sleep(0.5)  
        return True

    # Stolen from http://www.cs.rpi.edu/~goldsd/docs/spring2012-csci4220/websocket-py.txt
    def sendMessage(self, s):
        """
        Encode and send a WebSocket message
        """

        # Empty message to start with
        message = ""

        # always send an entire message as one frame (fin)
        b1 = 0x80

        # in Python 2, strs are bytes and unicodes are strings
        if type(s) == unicode:
            b1 |= TEXT
            payload = s.encode("UTF8")

        elif type(s) == str:
            b1 |= TEXT
            payload = s

        # Append 'FIN' flag to the message
        message += chr(b1)

        # never mask frames from the server to the client
        b2 = 0

        # How long is our payload?
        length = len(payload)
        if length < 126:
            b2 |= length
            message += chr(b2)

        elif length < (2 ** 16) - 1:
            b2 |= 126
            message += chr(b2)
            l = struct.pack(">H", length)
            message += l

        else:
            l = struct.pack(">Q", length)
            b2 |= 127
            message += chr(b2)
            message += l

        # Append payload to message
        message += payload

        # Send to the client
        self.client.send(str(message))

    # Stolen from http://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side
    def decodeCharArray(self, stringStreamIn):

        # Turn string values into opererable numeric byte values
        byteArray = [ord(character) for character in stringStreamIn]
        datalength = byteArray[1] & 127
        indexFirstMask = 2

        if datalength == 126:
            indexFirstMask = 4
        elif datalength == 127:
            indexFirstMask = 10

        # Extract masks
        masks = [m for m in byteArray[indexFirstMask: indexFirstMask + 4]]
        indexFirstDataByte = indexFirstMask + 4

        # List of decoded characters
        decodedChars = []
        i = indexFirstDataByte
        j = 0

        # Loop through each byte that was received
        while i < len(byteArray):
            # Unmask this byte and add to the decoded buffer
            decodedChars.append(chr(byteArray[i] ^ masks[j % 4]))
            i += 1
            j += 1

        # Return the decoded string
        return decodedChars

    # Handshake with this client
    def dohandshake(self, header, key=None):

        logging.debug("Begin handshake: %s" % header)

        # Get the handshake template
        handshake = self.handshake

        # Step through each header
        for line in header.split('\r\n')[1:]:
            name, value = line.split(': ', 1)

            # If this is the key
            if name.lower() == "sec-websocket-key":
                # Append the standard GUID and get digest
                combined = value + MAGIC
                response = base64.b64encode(hashlib.sha1(combined).digest())

                # Replace the placeholder in the handshake response
                handshake = handshake % {'acceptstring': response}

        logging.debug("Sending handshake %s" % handshake)
        self.client.send(handshake)
        return True

    def onmessage(self, data):
        # logging.info("Got message: %s" % data)
        self.send(data)

    def send(self, data):
        logging.info("Sent message: %s" % data)
        self.client.send("\x00%s\xff" % data)    
    
    def close(self):
        self.client.close()


# WebSocket server implementation
class WebSocketServer(object):
    # Constructor
    def __init__(self, bind, port, cls):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.socket.bind((bind, port))
        self.bind = bind
        self.port = port
        self.cls = cls
        self.connections = {}
        self.listeners = [self.socket]

    # Listen for requests
    def listen(self, backlog=5):

        self.socket.listen(backlog)
        logging.info("Listening on %s" % self.port)

        # Keep serving requests
        self.running = True
        while self.running:

            # Find clients that need servicing
            rList, wList, xList = select(self.listeners, [], self.listeners, 1)
            for ready in rList:
                if ready == self.socket:
                    logging.debug("New client connection")
                    client, address = self.socket.accept()
                    fileno = client.fileno()
                    self.listeners.append(fileno)
                    self.connections[fileno] = self.cls(client, self)
                else:
                    logging.debug("Client ready for reading %s" % ready)
                    client = self.connections[ready].client
                    try:
                        data = client.recv(1024)
                    except Exception, e:
                        logging.error(str(e))
                        data = ''
                    fileno = client.fileno()
                    if data:
                        self.connections[fileno].feed(data)
                    else:
                        logging.debug("Closing client %s" % ready)
                        self.connections[fileno].close()
                        del self.connections[fileno]
                        self.listeners.remove(ready)

            # Step though and delete broken connections
            for failed in xList:
                if failed == self.socket:
                    logging.error("Socket broke")
                    for fileno, conn in self.connections:
                        conn.close()
                    self.running = False


# Entry point
if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    server = WebSocketServer("", 8888, WebSocket)
    server_thread = Thread(target=server.listen, args=[5])
    server_thread.start()	

    # Add SIGINT handler for killing the threads
    def signal_handler(signal, frame):
        logging.info("Caught Ctrl+C, shutting down...")
        server.running = False
        sys.exit()


    signal.signal(signal.SIGINT, signal_handler)

    while True:
        time.sleep(100)

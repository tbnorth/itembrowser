#-----------------------------------------------------------
#
# Item Browser is a QGIS plugin which allows you to browse a multiple selection.
#
# Copyright    : (C) 2013 Denis Rouzaud
# Email        : denis.rouzaud@gmail.com
#
#-----------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this progsram; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#---------------------------------------------------------------------

from PyQt4.QtCore import QUrl, Qt
from PyQt4.QtGui import QAction, QIcon, QDesktopServices
from qgis.core import QgsMapLayer, QgsProject

from core.mysettings import MySettings
from gui.mysettingsdialog import MySettingsDialog
from gui.itembrowserdock import ItemBrowserDock

import resources

# for server
import socket
import os
import lproto
    
class itemBrowser():
    def __init__(self, iface):
        self.iface = iface
        self.settings = MySettings()
        self.docks = {}

        self.init_server()
        
    def dispatch_script(self, msg, ses):
        msg = str(msg)
        print("leoremote.py: dispatch script", msg)
        
        if msg == "list":
            print 'listing'
            print('\n'.join(i.layer.name() for i in self.docks.values()))
            return
        
        cmd = msg.split()
        
        key = [k for k in self.docks 
               if self.docks[k].layer.name() == cmd[0]][0]
        dock = self.docks[key]
        
        if cmd[1] == 'first':
            dock.on_firstButton_clicked()
        if cmd[1] == 'last':
            dock.on_lastButton_clicked()
        
        return
        fd, pth = tempfile.mkstemp(suffix='.py')
        f = os.fdopen(fd,"w")
        f.write(msg)
        f.close()
        # first run
        if 'pydict' not in ses:
            ses['pydict'] = {'g' : g }
    
        # print("run file",pth)
        execfile(pth, ses['pydict'])
        # print("run done")
    
        
    def init_server(self):
        
        self.lps = lproto.LProtoServer()
        self.lps.set_receiver(self.dispatch_script)

        # EKR: 2011/10/12
        if hasattr(socket,'AF_UNIX'):
            uniqid = 'leoserv-%d' % os.getpid()
        else:
            uniqid = '172.16.0.0',1
        
        self.lps.listen(uniqid)
        
        fullpath = self.lps.srv.fullServerName()
        socket_file = os.path.expanduser('/tmp/ib_sockname')
        open(socket_file,'w').write(fullpath)
        print('leoremote.py: file:   %s' % socket_file)
        print('leoremote.py: server: %s' % fullpath)


    def initGui(self):
        # browse action
        self.browserAction = QAction(QIcon(":/plugins/itembrowser/icons/itembrowser.svg"),
                                     "Browse selected items of current layer", self.iface.mainWindow())
        self.browserAction.setEnabled(True)
        self.browserAction.triggered.connect(lambda(x): self.openBrowserDock())  # prevent passing "False" to the method
        self.iface.addToolBarIcon(self.browserAction)
        self.iface.addPluginToMenu("&Item Browser", self.browserAction)
        # settings
        self.uisettingsAction = QAction(QIcon(":/plugins/itembrowser/icons/settings.svg"), "settings",
                                        self.iface.mainWindow())
        self.uisettingsAction.triggered.connect(self.showSettings)
        self.iface.addPluginToMenu("&Item Browser", self.uisettingsAction)     
        # help
        self.helpAction = QAction(QIcon(":/plugins/itembrowser/icons/help.svg"), "Help", self.iface.mainWindow())
        self.helpAction.triggered.connect(lambda: QDesktopServices().openUrl(QUrl("http://3nids.github.io/itembrowser")))
        self.iface.addPluginToMenu("&Item Browser", self.helpAction)

        QgsProject.instance().readProject.connect(self.reloadSession)
    def unload(self):
        self.iface.removePluginMenu("&Item Browser", self.browserAction)
        self.iface.removePluginMenu("&Item Browser", self.uisettingsAction)
        self.iface.removePluginMenu("&Item Browser", self.helpAction)
        self.iface.removeToolBarIcon(self.browserAction)
        
    def openBrowserDock(self, layer=None, currentFeature=0):
        if layer is None:
            layer = self.iface.legendInterface().currentLayer()
        if layer is None:
            return
        if layer.id() in self.docks:
            #print "layer already docked"
            return
        dock = ItemBrowserDock(self.iface, layer, currentFeature)
        dock.dockRemoved.connect(self.dockRemoved)
        if self.settings.value("dockArea") == 1:
            self.iface.addDockWidget(Qt.RightDockWidgetArea, dock)
        else:
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.docks[layer.id()] = dock

    def dockRemoved(self, layerid):
        del self.docks[layerid]

    def reloadSession(self):
        if not self.settings.value("saveSelectionInProject"):
            return
        for layer in self.iface.legendInterface().layers():
            exec("selection = %s" % layer.customProperty("itemBrowserSelection", "[]"))
            if len(selection) > 0:
                currentFeature = long(layer.customProperty("itemBrowserCurrentItem", 0))
                if layer.id() in self.docks:
                    self.docks[layer.id()].listCombo.setCurrentIndex(currentFeature)
                else:
                    layer.setSelectedFeatures(selection)
                    self.openBrowserDock(layer, currentFeature)

    def showSettings(self):
        MySettingsDialog().exec_()





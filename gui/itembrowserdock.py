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

from PyQt4.QtCore import SIGNAL, pyqtSlot, pyqtSignal, Qt
from PyQt4.QtGui import QDockWidget, QIcon, QAction
from qgis.core import QgsPoint, QgsRectangle, QgsFeatureRequest, QgsFeature
from qgis.gui import QgsRubberBand

from ..core.mysettings import MySettings
from ..ui.ui_itembrowser import Ui_itembrowser


class ItemBrowserDock(QDockWidget, Ui_itembrowser):
    dockRemoved = pyqtSignal(str)

    def __init__(self, iface, layer, currentFeature):
        self.iface = iface
        self.layer = layer
        self.renderer = self.iface.mapCanvas().mapRenderer()
        self.settings = MySettings()
        QDockWidget.__init__(self)
        self.setupUi(self)

        self.setWindowTitle("ItemBrowser: %s" % layer.name())
        if layer.hasGeometryType() is False:
            self.panCheck.setChecked(False)
            self.panCheck.setEnabled(False)
            self.scaleCheck.setChecked(False)
            self.scaleCheck.setEnabled(False)

        self.previousButton.setArrowType(Qt.LeftArrow)
        self.nextButton.setArrowType(Qt.RightArrow)
        icon = QIcon(":/plugins/itembrowser/icons/openform.svg")
        self.editFormButton.setIcon(icon)

        # actions
        icon = QIcon(":/plugins/itembrowser/icons/action.svg")
        self.actionButton.setIcon(icon)
        self.attrAction = layer.actions()
        actions = [self.attrAction[i] for i in range(self.attrAction.size())]
        preferredAction = layer.customProperty("ItemBrowserPreferedAction", "")
        if preferredAction not in actions:
            dfltAction = self.attrAction.defaultAction()
            if dfltAction > len(actions):
                preferredAction = self.attrAction[dfltAction].name()
        preferredActionFound = False
        for i, action in enumerate(actions):
            qAction = QAction(QIcon(":/plugins/itembrowser/icons/action.svg"), action.name(), self)
            qAction.triggered.connect(lambda: self.doAction(i))
            self.actionButton.addAction(qAction)
            if action.name() == preferredAction:
                self.actionButton.setDefaultAction(qAction)
                preferredActionFound = True
        if len(actions) == 0:
            self.actionButton.setEnabled(False)
        elif not preferredActionFound:
            self.actionButton.setDefaultAction(self.actionButton.actions()[0])

        self.rubber = QgsRubberBand(self.iface.mapCanvas())
        self.selectionChanged()
        self.getAttributeList()
        if currentFeature == self.listCombo.currentIndex():
            self.on_listCombo_currentIndexChanged(currentFeature)
        else:
            self.listCombo.setCurrentIndex(currentFeature)
        self.layer.layerDeleted.connect(self.close)
        self.layer.selectionChanged.connect(self.selectionChanged)

    def closeEvent(self, e):
        self.rubber.reset()
        self.layer.layerDeleted.disconnect(self.close)
        self.layer.selectionChanged.disconnect(self.selectionChanged)
        if self.settings.value("saveSelectionInProject"):
            self.layer.setCustomProperty("itemBrowserSelection", repr([]))
        self.dockRemoved.emit(self.layer.id())
          
    def selectionChanged(self):
        self.cleanBrowserFields()
        self.rubber.reset()
        nItems = self.layer.selectedFeatureCount()
        if nItems < 2:
            self.close()
            self.layer.emit(SIGNAL("browserNoItem()"))
            return
        self.browseFrame.setEnabled(True)
        self.subset = self.layer.selectedFeaturesIds()
        if self.settings.value("saveSelectionInProject"):
            self.layer.setCustomProperty("itemBrowserSelection", repr(self.subset))
        for fid in self.subset:
            self.listCombo.addItem("%u" % fid)

    def cleanBrowserFields(self):
        self.currentPosLabel.setText('0/0')
        self.listCombo.clear()
          
    def panScaleToItem(self, feature):
        if self.panCheck.isChecked() is False:
            return
        featBobo = feature.geometry().boundingBox()
        # if scaling and bobo has width and height (i.e. not a point)
        if self.scaleCheck.isChecked() and featBobo.width() != 0 and featBobo.height() != 0:
            featBobo.scale(self.settings.value("scale"))
            ul = self.renderer.layerToMapCoordinates(self.layer, QgsPoint(featBobo.xMinimum(), featBobo.yMaximum()))
            ur = self.renderer.layerToMapCoordinates(self.layer, QgsPoint(featBobo.xMaximum(), featBobo.yMaximum()))
            ll = self.renderer.layerToMapCoordinates(self.layer, QgsPoint(featBobo.xMinimum(), featBobo.yMinimum()))
            lr = self.renderer.layerToMapCoordinates(self.layer, QgsPoint(featBobo.xMaximum(), featBobo.yMinimum()))
            x = (ul.x(), ur.x(), ll.x(), lr.x())
            y = (ul.y(), ur.y(), ll.y(), lr.y())
            x0 = min(x)
            y0 = min(y)
            x1 = max(x)
            y1 = max(y)
        else:
            panTo = self.renderer.layerToMapCoordinates(self.layer, featBobo.center())
            mapBobo = self.iface.mapCanvas().extent()
            xshift = panTo.x() - mapBobo.center().x()
            yshift = panTo.y() - mapBobo.center().y()
            x0 = mapBobo.xMinimum() + xshift
            y0 = mapBobo.yMinimum() + yshift
            x1 = mapBobo.xMaximum() + xshift
            y1 = mapBobo.yMaximum() + yshift
        self.iface.mapCanvas().setExtent(QgsRectangle(x0, y0, x1, y1))
        self.iface.mapCanvas().refresh()

    def getCurrentItem(self):
        i = self.listCombo.currentIndex()
        if i == -1:
            return None
        f = QgsFeature()
        if self.layer.getFeatures(QgsFeatureRequest().setFilterFid(self.subset[i])).nextFeature(f):
            return f
        else:
            raise NameError("feature not found")

    def getAttributeList(self):
        """getAttributeList - load layers attributes into attribute selector 
        """

        self.selectAttribute.addItem("[ID]")
        for field in self.layer.dataProvider().fields():
            self.selectAttribute.addItem(field.name())
    def doAction(self, i):
        f = self.getCurrentItem()
        self.actionButton.setDefaultAction(self.actionButton.actions()[i])
        self.layer.setCustomProperty("ItemBrowserPreferedAction", self.attrAction[i].name())
        self.attrAction.doActionFeature(i, f)

    @pyqtSlot(name="on_previousButton_clicked")
    def previousFeaature(self):
        self.nextFeature(delta=-1)
          
    @pyqtSlot(name="on_nextButton_clicked")
    def nextFeature(self, delta=1):
        i = self.listCombo.currentIndex()
        c = self.listCombo.count()
        n = max(0, min(i+delta, c-1))
        self.listCombo.setCurrentIndex(n)
        self.saveCurrentFeature(n)

    @pyqtSlot(int, name="on_listCombo_activated")
    def saveCurrentFeature(self, i):
        if self.settings.value("saveSelectionInProject"):
            self.layer.setCustomProperty("itemBrowserCurrentItem", i)

    @pyqtSlot(int, name="on_listCombo_currentIndexChanged")
    def on_listCombo_currentIndexChanged(self, i):
        feature = self.getCurrentItem()
        if feature is None: 
            return
        self.rubber.reset()
        if self.listCombo.count() > 1:
            width = self.settings.value("rubberWidth")
            color = self.settings.value("rubberColor")
            self.rubber.setColor(color)
            self.rubber.setWidth(width)
            self.rubber.setToGeometry(feature.geometry(), self.layer)
        # scale to feature
        self.panScaleToItem(feature)
        # Update browser
        self.currentPosLabel.setText("%u/%u" % (i+1, len(self.subset)))
        # emit signal
        self.layer.emit(SIGNAL("browserCurrentItem(long)"), feature.id())
          
    @pyqtSlot(int, name="on_panCheck_stateChanged")
    def on_panCheck_stateChanged(self, i):
        if self.panCheck.isChecked():
            self.scaleCheck.setEnabled(True)
            feature = self.getCurrentItem()
            if feature is None:
                return
            self.panScaleToItem(feature)
        else:
            self.scaleCheck.setEnabled(False)
               
    @pyqtSlot(int, name="on_scaleCheck_stateChanged")
    def on_scaleCheck_stateChanged(self, i):
        if self.scaleCheck.isChecked():
            feature = self.getCurrentItem()
            if feature is None: 
                return
            self.panScaleToItem(feature)

    @pyqtSlot(int, name="on_selectAttribute_currentIndexChanged")
    def on_selectAttribute_currentIndexChanged(self, index):
        """on_selectAttribute_currentIndexChanged - different attribute
        selected 

        :Parameters:
        - `index`: combo box item index
        """

        if self.selectAttribute.count() == 1:
            return  # happens when first entry added

        field = self.selectAttribute.currentText()
        for n, fid in enumerate(self.subset):
            if field == "[ID]":
                self.listCombo.setItemText(n, str(fid))
            else:
                feature = next(
                    self.layer.getFeatures(QgsFeatureRequest().setFilterFid(fid)))
                self.listCombo.setItemText(n, str(feature[field]))
    @pyqtSlot(name="on_sortUp_clicked")
    def on_sortUp_clicked(self, reverse=False):
        """on_sortUp_clicked - sort list upwards
        """
        order = []
        # faster to just sort self.listCombo text items, but
        # then numbers would be sorted as text, 100.3 < 2.1 etc.
        field = self.selectAttribute.currentText()
        for n, fid in enumerate(self.subset):
            if field == "[ID]":
                order.append( (fid, n) )
            else:
                feature = next(
                    self.layer.getFeatures(QgsFeatureRequest().setFilterFid(fid)))
                order.append( (feature[field], n) )
        
        order.sort(reverse=reverse)
        old_fid = self.subset[self.listCombo.currentIndex()]
        self.subset = [self.subset[i[1]] for i in order]
        for n in range(self.listCombo.count()):
            self.listCombo.setItemText(n, str(order[n][0]))
        self.listCombo.setCurrentIndex(self.subset.index(old_fid))
    @pyqtSlot(name="on_sortDown_clicked")
    def on_sortDown_clicked(self):
        """on_sortDown_clicked - sort list diwnwards
        """
        self.on_sortUp_clicked(reverse=True)
    @pyqtSlot(name="on_lastButton_clicked")
    def on_lastButton_clicked(self):
        """on_lastButton_clicked - jump to last item in list
        """
        self.listCombo.setCurrentIndex(self.listCombo.count()-1)
    @pyqtSlot(name="on_firstButton_clicked")
    def on_firstButton_clicked(self):
        """on_firstButton_clicked - jump to first item in list
        """
        self.listCombo.setCurrentIndex(0)
    @pyqtSlot(name="on_next5Button_clicked")
    def on_next5Button_clicked(self):
        """on_next5Button_clicked - jump forward 5% of the list
        """
        step = max(self.listCombo.count() // 20, 1)  # don't advance zero items
        self.nextFeature(delta=step)
    @pyqtSlot(name="on_previous5Button_clicked")
    def on_previous5Button_clicked(self):
        """on_previous5Button_clicked - jump back 5% of the list
        """
        step = max(self.listCombo.count() // 20, 1)  # don't advance zero items
        self.nextFeature(delta=-step)
    @pyqtSlot(name="on_editFormButton_clicked")
    def openFeatureForm(self):
        self.iface.openFeatureForm(self.layer, self.getCurrentItem())

from jsonrpcclient.requests import Request
from requests import post, get
from decimal import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

import sys, getopt, argparse, json, time, getpass, os.path
from util import *
from rvn_rpc import *

from server_connection import *

PAGE_SIZE = 25

class ServerOrdersDialog(QDialog):
  def __init__(self, server_connection, parent=None, **kwargs):
    super().__init__(parent, **kwargs)
    uic.loadUi("ui/qt/server_orders.ui", self)
    self.server = server_connection
    self.server_offset = 0
    self.actionRefresh.trigger()

  def prev_page(self):
    if self.server_offset - PAGE_SIZE > 0:
      self.server_offset -= PAGE_SIZE

  def next_page(self):
    if self.server_offset + PAGE_SIZE < self.orders["totalCount"]:
      self.server_offset += PAGE_SIZE

  def refresh_listings(self):
    self.orders = self.server.search_listings(asset_name=self.txtSearch.text())
    self.swaps = self.orders["swaps"]
    self.lstServerOrders.clear()
    self.lblStatus.setText("{}-{}/{}".format(self.orders["offset"], self.orders["offset"] + len(self.swaps), self.orders["totalCount"] ))
    for swap in self.swaps:
      self.add_server_order(self.lstServerOrders, swap)
    
    self.btnPrev.setEnabled(self.server_offset > 0)
    self.btnNext.setEnabled(self.server_offset + PAGE_SIZE < self.orders["totalCount"])

  def add_server_order(self, list, server_order):
    orderWidget = QServerOrderWidget(server_order)
    orderItem = QListWidgetItem(list)
    orderItem.setSizeHint(orderWidget.sizeHint())
    list.addItem(orderItem)
    list.setItemWidget(orderItem, orderWidget)


class QServerOrderWidget (QWidget):
  def __init__ (self, server_listing, parent = None):
    super(QServerOrderWidget, self).__init__(parent)
    
    self.textQVBoxLayout = QVBoxLayout()
    self.upText    = QLabel()
    self.downText  = QLabel()
    self.textQVBoxLayout.addWidget(self.upText)
    self.textQVBoxLayout.addWidget(self.downText)
    self.allQHBoxLayout  = QHBoxLayout()
    self.btnActivate     = QPushButton()
    self.allQHBoxLayout.addLayout(self.textQVBoxLayout, 0)
    self.allQHBoxLayout.addWidget(self.btnActivate, 1)
    self.setLayout(self.allQHBoxLayout)

    #Need to reverse perspective for external orders
    if server_listing["orderType"] == SERVER_TYPE_BUY:
      self.upText.setText("Sell: {}x [{}]".format(server_listing["outQuantity"], server_listing["outType"]))
      self.downText.setText("Price: {}x RVN".format(server_listing["inQuantity"]))
      self.btnActivate.setText("Sell {}".format(server_listing["outType"]))
    elif server_listing["orderType"] == SERVER_TYPE_SELL:
      self.upText.setText("Buy: {}x [{}]".format(server_listing["inQuantity"], server_listing["inType"]))
      self.downText.setText("Price: {}x RVN".format(server_listing["outQuantity"]))
      self.btnActivate.setText("Buy {}".format(server_listing["inType"]))
    elif server_listing["orderType"] == SERVER_TYPE_TRADE:
      self.upText.setText("Trade: {}x [{}]".format(server_listing["inQuantity"], server_listing["inType"]))
      self.downText.setText("Price: {}x [{}]".format(server_listing["outQuantity"], server_listing["outType"]))
      self.btnActivate.setText("Trade for {}".format(server_listing["inType"]))
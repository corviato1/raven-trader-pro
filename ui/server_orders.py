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
  def __init__(self, server_connection, prefill=None, parent=None, **kwargs):
    super().__init__(parent, **kwargs)
    uic.loadUi("ui/qt/server_orders.ui", self)
    self.server = server_connection
    self.server_offset = 0
    self.cmbOrderType.addItems(["All Orders", "Buy Orders Only", "Sell Orders Only", "Trade Orders Only"])

    if prefill:
      self.txtSearch.setText(prefill["asset"]) if "asset" in prefill else None

  def prev_page(self):
    if self.server_offset - PAGE_SIZE >= 0:
      self.server_offset -= PAGE_SIZE
    self.refresh_listings()

  def next_page(self):
    if self.server_offset + PAGE_SIZE < self.orders["totalCount"]:
      self.server_offset += PAGE_SIZE
    self.refresh_listings()

  def full_reset(self):
    self.grouped_mode = self.chkCombineOrders.isChecked()
    self.cmbOrderType.setEnabled(not self.grouped_mode)
    self.server_offset = 0
    self.refresh_listings()

  def refresh_listings(self):
    print("Refreshing Server Orders")
    swap_type = None
    #Have to reverse perspective when looking at external orders
    if self.cmbOrderType.currentText() == "Buy Orders Only":
      swap_type = SERVER_TYPE_SELL
    elif self.cmbOrderType.currentText() == "Sell Orders Only":
      swap_type = SERVER_TYPE_BUY
    elif self.cmbOrderType.currentText() == "Trade Orders Only":
      swap_type = SERVER_TYPE_TRADE

    QApplication.setOverrideCursor(Qt.WaitCursor)
    if self.grouped_mode:
      self.orders = self.server.search_listings_grouped(asset_name=self.txtSearch.text(), offset=self.server_offset, page_size=PAGE_SIZE)
      self.swaps = self.orders["assets"]
    else:
      self.orders = self.server.search_listings(asset_name=self.txtSearch.text(), swap_type=swap_type, offset=self.server_offset, page_size=PAGE_SIZE)
      self.swaps = self.orders["swaps"]
    QApplication.restoreOverrideCursor()

    self.lstServerOrders.clear()
    self.lblStatus.setText("{}-{}/{}".format(self.orders["offset"] + 1, self.orders["offset"] + len(self.swaps), self.orders["totalCount"] ))
    for swap in self.swaps:
      self.add_server_order(self.lstServerOrders, swap)
    
    self.btnPrev.setEnabled(self.server_offset > 0)
    self.btnNext.setEnabled(self.server_offset + PAGE_SIZE < self.orders["totalCount"])

  def execute_order(self, order):
    self.selected_order = order
    self.accept()

  def view_orders(self, asset_name):
    self.txtSearch.setText(asset_name)
    self.chkCombineOrders.setChecked(False)
    self.full_reset()

  def add_server_order(self, list, server_order):
    widget_class = QServerTradeWidget if self.grouped_mode else QServerOrderWidget
    orderWidget = widget_class(server_order, self.execute_order, self.view_orders)
    orderItem = QListWidgetItem(list)
    orderItem.setSizeHint(orderWidget.sizeHint())
    list.addItem(orderItem)
    list.setItemWidget(orderItem, orderWidget)


class QServerOrderWidget (QWidget):
  def __init__ (self, server_listing, fnExecuteOrder=None, fnViewOrders=None, parent = None):
    super(QServerOrderWidget, self).__init__(parent)
    
    self.fn_execute_order = fnExecuteOrder
    self.fn_view_orders = fnViewOrders
    self.textQVBoxLayout = QVBoxLayout()
    self.upText    = QLabel()
    self.downText  = QLabel()
    self.textQVBoxLayout.addWidget(self.upText)
    self.textQVBoxLayout.addWidget(self.downText)
    self.allQHBoxLayout  = QHBoxLayout()
    self.btnActivate     = QPushButton()
    self.allQHBoxLayout.addLayout(self.textQVBoxLayout, stretch=5)
    self.allQHBoxLayout.addWidget(self.btnActivate, stretch=1)
    self.setLayout(self.allQHBoxLayout)

    self.btnActivate.clicked.connect(lambda _, order=server_listing: self.fn_execute_order(order))

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



class QServerTradeWidget (QWidget):
  def __init__ (self, server_grouping, fnExecuteOrder=None, fnViewOrders=None, parent = None):
    super(QServerTradeWidget, self).__init__(parent)
    
    self.fn_execute_order = fnExecuteOrder
    self.fn_view_orders = fnViewOrders
    self.data = server_grouping
    self.textQVBoxLayout = QVBoxLayout()
    self.lblName        = QLabel()
    self.lblBuySummary  = QLabel()
    self.lblSellSummary = QLabel()
    self.textQVBoxLayout.addWidget(self.lblName)
    self.textQVBoxLayout.addWidget(self.lblBuySummary)
    self.textQVBoxLayout.addWidget(self.lblSellSummary)

    self.allQHBoxLayout   = QHBoxLayout()
    self.btnBuy           = QPushButton()
    self.btnSell          = QPushButton()
    self.btnMore          = QPushButton()
    self.allQHBoxLayout.addLayout(self.textQVBoxLayout, stretch=5)
    self.allQHBoxLayout.addWidget(self.btnBuy, stretch=3)
    self.allQHBoxLayout.addWidget(self.btnSell, stretch=3)
    self.allQHBoxLayout.addWidget(self.btnMore, stretch=1)
    self.setLayout(self.allQHBoxLayout)

    self.lblName.setText(self.data["asset"])
    self.lblBuySummary.setText("Buy: {}".format(self.data["buyQuantity"]))
    self.lblSellSummary.setText("Sell: {}".format(self.data["sellQuantity"]))

    if self.data["minBuy"]:
      min_buy = self.data["minBuy"]
      self.btnBuy.setText("Buy {}\n{} RVN".format(min_buy["inQuantity"], min_buy["outQuantity"]))
      self.btnBuy.setEnabled(True)
    else:
      self.btnBuy.setText("No Buy\nAvailable")
      self.btnBuy.setEnabled(False)
    
    if self.data["maxSell"]:
      max_sell = self.data["maxSell"]
      self.btnSell.setText("Sell {}\n{} RVN".format(max_sell["outQuantity"], max_sell["inQuantity"]))
      self.btnSell.setEnabled(True)
    else:
      self.btnSell.setText("No Sell\nAvailable")
      self.btnSell.setEnabled(False)
    
    self.btnMore.setText("...")
    self.btnMore.setToolTip("View all orders for this asset.")

    self.btnBuy.clicked.connect(lambda _, group=server_grouping: call_if_set(self.fn_execute_order, group["minBuy"]))
    self.btnSell.clicked.connect(lambda _, group=server_grouping: call_if_set(self.fn_execute_order, group["maxSell"]))
    self.btnMore.clicked.connect(lambda _, group=server_grouping: call_if_set(self.fn_view_orders, group["asset"]))
from jsonrpcclient.requests import Request
from requests import post, get
from decimal import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

import sys, getopt, argparse, json, time, getpass, os.path
from util import *

from app_settings import AppSettings

def test_rpc_status():
    #Then do a basic test of RPC, also can check it is synced here
  chain_info = do_rpc("getblockchaininfo")
  #If the headers and blocks are not within 5 of each other,
  #then the chain is likely still syncing
  chain_updated = False if not chain_info else\
    (chain_info["headers"] - chain_info["blocks"]) < 5
  
  if chain_info and chain_updated:
    #Determine if we are on testnet, and write back to settings.
    AppSettings.instance.rpc_set_testnet(chain_info["chain"] == "test")
    return True
  elif chain_info:
    show_error("Sync Error", 
    "Server appears to not be fully synchronized. Must be at the latest tip to continue.",
    "Network: {}\r\nCurrent Headers: {}\r\nCurrent Blocks: {}".format(chain_info["chain"], chain_info["headers"], chain_info["blocks"]))
  else:
    show_error("Error connecting", 
    "Error connecting to RPC server.\r\n{}".format(AppSettings.instance.rpc_url()), 
    "Make sure the following configuration variables are in your raven.conf file"+
    "\r\n\r\nserver=1\r\nrpcuser={}\r\nrpcpassword={}".format(AppSettings.instance.rpc_details()["user"], AppSettings.instance.rpc_details()["password"]))
  return False

def do_rpc(method, log_error=True, **kwargs):
  req = Request(method, **kwargs)
  try:
    url = AppSettings.instance.rpc_url()
    resp = post(url, json=req)
    if resp.status_code != 200 and log_error:
      print("RPC ==>", end="")
      print(req)
      print("RPC <== ERR:", end="")
      print(resp.text)
    if resp.status_code != 200:
      return None
    return json.loads(resp.text)["result"]
  except:
    print("RPC Error")
    return None

def decode_full(txid):
  local_decode = do_rpc("getrawtransaction", log_error=False, txid=txid, verbose=True)
  if local_decode:
    result = local_decode
  else:
    rpc = AppSettings.instance.rpc_details()
    #TODO: Better way of handling full decode
    tx_url = "https://rvnt.cryptoscope.io/api/getrawtransaction/?txid={}&decode=1" if rpc["testnet"]\
      else "https://rvn.cryptoscope.io/api/getrawtransaction/?txid={}&decode=1"
    print("Query Full: {}".format(tx_url.format(txid)))
    print(rpc)
    resp = get(tx_url.format(txid))
    if resp.status_code != 200:
      print("Error fetching raw transaction")
    result = json.loads(resp.text)
  return result

def check_unlock(timeout = 10):
  rpc = AppSettings.instance.rpc_details()
  phrase_test = do_rpc("help", command="walletpassphrase")
  #returns None if no password set
  if(phrase_test.startswith("walletpassphrase")):
    print("Unlocking Wallet for {}s".format(timeout))
    do_rpc("walletpassphrase", passphrase=rpc["unlock"], timeout=timeout)

def dup_transaction(tx):
  new_vin = []
  new_vout = {}
  for old_vin in tx["vin"]:
    new_vin.append({"txid": old_vin["txid"], "vout": old_vin["vout"], "sequence": old_vin["sequence"]})
  for old_vout in sorted(tx["vout"], key=lambda vo: vo["n"]):
    vout_script = old_vout["scriptPubKey"]
    vout_addr = vout_script["addresses"][0]
    if("asset" in vout_script):
      new_vout[vout_addr] = make_transfer(vout_script["asset"]["name"], vout_script["asset"]["amount"])
    else:
      new_vout[vout_addr] = old_vout["value"]
  return new_vin, new_vout

def search_swap_tx(utxo):
  (txid, vout) = split_utxo(utxo)
  wallet_tx = do_rpc("listtransactions", account="", count=10)
  for tx in wallet_tx:
    details = do_rpc("getrawtransaction", txid=tx["txid"], verbose=True)
    for tx_vin in details["vin"]:
      if ("txid" in tx_vin and "vout" in tx_vin) and \
        (tx_vin["txid"] == txid and tx_vin["vout"] == vout):
        return tx
  print("Unable to find transaction for completed swap")
  return None #If we don't find it 10 blocks back, who KNOWS what happened to it
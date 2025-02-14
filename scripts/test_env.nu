const CORE_USER = "nixblitz"
const CORE_PASSWORD = "nixblitz"
const CORE_RAW_TX_ADDRESS = "tcp://127.0.0.1:28332"
const CORE_RAW_BLOCK_ADDRESS = "tcp://127.0.0.1:28333"

const BASE_DIR = "test_env_data"
const CORE_DIR = $"($BASE_DIR)/bitcoin"
const LND_DIR = $"($BASE_DIR)/lnd"
const CLN_DIR = $"($BASE_DIR)/cln"

# init the bitcon core daemon in regtest mode
def init_env [] {
  print "Creating wallet \"testwallet\", if not created yet..."
  bitcli createwallet testwallet out+err>| ignore

  print "Loading wallet \"testwallet\", if not loaded yet..."
  bitcli loadwallet testwallet out+err>| ignore
}

#  regtest command for bitcoin core
def bitcli --wrapped [...args] {
  let coreDir = $"(pwd)/($CORE_DIR)"
  bitcoin-cli -regtest --datadir=($coreDir) ...$args
}

#  short for lncli with all connection settings applied
def lndcli --wrapped [...args] {
  (
    lncli --lnddir=(pwd)/($LND_DIR)
      --chain "bitcoin"
      --network "regtest"
      ...$args
  )
}

#  short for lightning-cli with all connection settings applied
def clncli --wrapped [...args] {
  let cwd = readlink -f .
  (
    lightning-cli
      --regtest
      --lightning-dir=(pwd)/($CLN_DIR)
      --rpc-file=(pwd)/($CLN_DIR)/regtest/lightning-rpc
      ...$args
  )
}

#  Sends a transaction using the default loaded wallet
def bitsend [
  address: string, # The address to send the funds to
  amount: float = 15.0 # The amount of funds to send in Bitcoin
  ] {
  bitcli -named -regtest sendtoaddress address=($address) amount=($amount) fee_rate=100
}

#  Generates regtest blocks
def bitgen [
  num_blocks: int=10 # The number of blocks to generate
  ] {
  bitcli -generate $num_blocks
}

#  Get the pubkey of the given node
def regpubkey [
  node: string # The node to get the pubkey of ("lnd" or "cln")
] {
  match $node {
    "cln" => { clncli getinfo | from json | echo $in.id }
    "lnd" => { lndcli getinfo | from json | echo $in.identity_pubkey }
    _ => { print "node must either be \"lnd\" or \"cln\"." }
  }
}

# Generate a new onchain address for the given node
def regaddress [
  node: string # The node to generate an address for ("lnd" or "cln")
] {
  match $node {
    "cln" => { clncli newaddr | from json | $in.bech32 }
    "lnd" => { lndcli newaddress np2wkh | from json | $in.address }
    _ => { print "node must either be \"lnd\" or \"cln\"." }
  }
}

# List funds in the given node
def reglistfunds [
  node: string # The node to list funds for ("lnd" or "cln")
] {
  match $node {
    "cln" => { clncli listfunds | from json | echo $in }
    "lnd" => {
      let channel_balance = lndcli channelbalance | from json
      let wallet_balance = lndcli walletbalance | from json
      echo {
        channel: $channel_balance,
        onchain: $wallet_balance
      }
    }
    _ => { print "node must either be \"lnd\" or \"cln\"." }
  }
}

# open a channel `to` the other node
def regopenchannel [
  to: string, # The node to open a channel to ("lnd" or "cln"). From will be the "other" node.
  local_amount: int = 10_000_000, # The amount in satoshis to commit to the channel
  push_amount: int = 5_000_000 # The amount in satoshis to push to the remote node as part of the channel opening
] {
  match $to {
    "cln" => {
      let k = (clnpubkey)
      lndcli openchannel $k --local_amt $local_amount --push_amt $push_amount
    }
    "lnd" => {
      let k = (lndpubkey)
      clncli fundchannel $k $local_amount
    }
    _ => { print "to must either be \"lnd\" or \"cln\"." }
  }
}

# fund all nodes with onchain testnet coins
def regfundnodes [
  amount: float = 15.0 # The amount of funds to send to the nodes
] {
  let cln = (regaddress "cln")
  let lnd = (regaddress "lnd")

  bitsend $cln $amount
  bitsend $lnd $amount
}

# generate a syntetic history by making random payments between nodes
def regmakehistory [
  rounds: int = 100 # How many rounds of history you want to make
] {
  for i in 0..$rounds {
    let from = (random int 0..3)
    mut to = (random int 0..3)
    while $from == $to {
      $to = (random int 0..3)
    }
  }
}

const CORE_USER = "nixblitz"
const CORE_PASSWORD = "nixblitz"
const CORE_RAW_TX_ADDRESS = "tcp://127.0.0.1:28332"
const CORE_RAW_BLOCK_ADDRESS = "tcp://127.0.0.1:28333"

const BASE_DIR = "test_env_data"
const CORE_DIR = $"($BASE_DIR)/bitcoin"
const LND_DIR = $"($BASE_DIR)/lnd"
const CLN_DIR = $"($BASE_DIR)/cln"

const ENV_FILE = '
BAPI_JWT_SECRET=please_please_update_me_please
BAPI_JWT_ALGORITHM=HS256
BAPI_JWT_EXPIRY_TIME=3600000
BAPI_ROOT_PATH = "/"
BAPI_LOG_LEVEL=INFO
BAPI_PLATFORM={{platform}}
BAPI_RB_SHELL_SCRIPT_PATH={{schell_script_path}}
BAPI_GATHER_HW_INFO_INTERVAL = 2
BAPI_CPU_USAGE_AVERAGING_PERIOD = 0.5
BAPI_GATHER_LN_INFO_INTERVAL = 5.0
BAPI_NETWORK=regtest
BAPI_BITCOIND_ADDRESS=127.0.0.1
BAPI_BITCOIND_PORT_RPC=18443
BAPI_BITCOIND_ZMQ_BLOCK_RPC="hashblock"
BAPI_BITCOIND_ZMQ_BLOCK_PORT=28333
BAPI_BITCOIND_USER=nixblitz
BAPI_BITCOIND_RPC_PW=nixblitz

BAPI_LN_NODE={{node_type}}

BAPI_LND_MACAROON={{lnd_macaroon}}
BAPI_LND_CERT={{lnd_cert}}
BAPI_LND_GRPC_IP=127.0.0.1
BAPI_LND_GRPC_PORT=10009

BAPI_CLN_JRPC_PATH={{cln_jrpc_path}}
BAPI_CLN_GRPC_CERT={{cln_cert}}
BAPI_CLN_GRPC_KEY={{cln_grpc_key}}
BAPI_CLN_GRPC_CA={{cln_grpc_ca}}
BAPI_CLN_GRPC_IP=127.0.0.1
BAPI_CLN_GRPC_PORT=9537
BAPI_NATIVE_LOGIN_PASSWORD=nixblitz

BAPI_REDIS_URL=redis://127.0.0.1:6379/0

BAPI_APP_STATUS_UPDATE_INTERVAL_MIN = 30
BAPI_CACHE_TTL_SECONDS = 2100
BAPI_LOCK_TTL_SECONDS = 300
'

# init the bitcon core daemon in regtest mode
def init_env [] {
  print "Creating wallet \"testwallet\", if not created yet..."
  bitcli createwallet testwallet out+err>| ignore

  print "Loading wallet \"testwallet\", if not loaded yet..."
  bitcli loadwallet testwallet out+err>| ignore
}

#  Generates a '.env' file for use with
#  Blitz Api using the local node.
#
#  Required: node options are "lnd" and "cln".
#
#  Platform options are "native_python", "raspiblitz" and "fake_blitz".
#  If no platform is specified, "native_python" is used.
#
#  NOTE: Run this in the directory where the
#        data folder is located (test_env_data)
#        as it'll be relative to that path
#
#  Example:
#  reg-mk-api-env lnd raspiblitz | save .env
def "reg-mk-api-env" [
    node: string = "lnd",  # The node to use
    platform: string = "native_python"  # The platform to use
] {
  let folders = (ls | where type == "dir" | get name)
  if not ($folders | any {|f| $f == $BASE_DIR}) {
    print $"Error: ($BASE_DIR) is not a subfolder of the current working directory."
    return
  }

  if ($node != "cln" and $node != "lnd") {
    print $"node must either be \"lnd\" or \"cln\". Got: ($node)"
    return
  }

  if ($platform != "native_python"
      and $platform != "raspiblitz"
      and $platform != "fake_blitz")  {
    print "node must either be \"native_python\", \"raspiblitz\" or \"fake_blitz\". Got: ($platform)"
    return
  }

  let platform_value = (if $platform == "raspiblitz" or $platform == "fake_blitz" { "raspiblitz" } else { "native_python" })
  let shell_script_path = (if $platform == "raspiblitz"  { "/home/admin" } else if $platform == "fake_blitz" { "./scripts/fake_blitz_scripts" } else { "/dev/null" })
  let replacements = {
    "{{platform}}": $platform_value,
    "{{schell_script_path}}": $shell_script_path,
    "{{node_type}}": (if $node == "lnd" { "lnd_grpc" } else { "cln_jrpc" }),
    "{{lnd_cert}}": $"(pwd)/($LND_DIR)/tls.cert",
    "{{lnd_macaroon}}": $"(pwd)/($LND_DIR)/data/chain/bitcoin/regtest/admin.macaroon",
    "{{cln_jrpc_path}}": $"(pwd)/($CLN_DIR)/regtest/lightning-rpc",
    "{{cln_cert}}": $"(pwd)/($CLN_DIR)/regtest/lightning-rpc",
  }
  let keys = ($replacements | transpose key value | each {|f| $f.key} | collect)
  mut file_content = $ENV_FILE
  for key in $keys {
    $file_content = $file_content | str replace $key ($replacements | get $key)
  }

  $file_content
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
      let k = regpubkey cln
      lndcli connect $"($k)@127.0.0.1:9736"
      lndcli openchannel --node_key $k --local_amt $local_amount --push_amt $push_amount
    }
    "lnd" => {
      let k = regpubkey lnd
      clncli fundchannel $"($k)@127.0.0.0:9735" $local_amount
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

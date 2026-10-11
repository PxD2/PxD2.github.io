"""PXD Crypto Pay: buyer pays the merchant's own wallet directly in USDC. PXD never holds the coins.

- The merchant's wallet address is pinned in its PXD certificate (pxdsign issue --wallet evm=0x...),
  so a copied or edited store cannot swap where the money goes.
- Each order gets an exact amount with a unique sub-cent tag (USDC has 6 decimals), so the
  gateway can recognize the payment on chain without ever touching the funds.
- The gateway only reads the chain (eth_blockNumber, eth_getLogs) to mark an order paid.
USDC contract addresses: Circle, developers.circle.com/stablecoins/usdc-contract-addresses (checked 2026-10-11).
"""
import hashlib, json, re, threading, time, urllib.request

CHAINS = {
    "base":     {"name": "Base",     "id": 8453,  "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "rpc": "https://mainnet.base.org"},
    "ethereum": {"name": "Ethereum", "id": 1,     "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "rpc": "https://ethereum-rpc.publicnode.com"},
    "polygon":  {"name": "Polygon",  "id": 137,   "usdc": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "rpc": "https://polygon-rpc.com"},
    "arbitrum": {"name": "Arbitrum", "id": 42161, "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "rpc": "https://arb1.arbitrum.io/rpc"},
}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # keccak256("Transfer(address,address,uint256)")
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
EXPIRE_S = 3600


class CryptoPay:
    def __init__(self, state_path, rpc_overrides=None, confirmations=3):
        self.path, self.conf, self.lock = state_path, confirmations, threading.Lock()
        self.rpc_url = {c: (rpc_overrides or {}).get(c) or v["rpc"] for c, v in CHAINS.items()}
        try:
            self.reqs = json.load(open(state_path))
        except (OSError, ValueError):
            self.reqs = {}

    def _save(self):
        tmp = self.path + ".tmp"
        json.dump(self.reqs, open(tmp, "w"), indent=1)
        import os; os.replace(tmp, self.path)

    def rpc(self, chain, method, params):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.rpc_url[chain], data=body, headers={"Content-Type": "application/json", "User-Agent": "PXD-Gateway/1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            out = json.load(r)
        if "error" in out:
            raise OSError(f"{chain} RPC: {out['error'].get('message', out['error'])}")
        return out["result"]

    @staticmethod
    def wallet_for(cert, chain):
        w = cert.get("wallets") or {}
        addr = w.get(f"usdc:{chain}") or w.get("evm")
        return addr if addr and ADDR.match(addr) else None

    def request(self, order, chain, to, cents, merchant):
        """A payment request for `cents` of USD in USDC to the merchant's own address."""
        if chain not in CHAINS:
            raise ValueError(f"chain must be one of {', '.join(CHAINS)}")
        c = CHAINS[chain]
        with self.lock:
            busy = {(r["chain"], r["to"].lower(), r["units"]) for r in self.reqs.values() if r["state"] == "waiting"}
            tag = int(hashlib.sha256(f"{order}{merchant}".encode()).hexdigest(), 16) % 9000 + 1000  # 0.001000 to 0.009999 USDC
            units = cents * 10_000 + tag
            while (chain, to.lower(), units) in busy:   # two open orders never share an amount
                units += 1
        block = int(self.rpc(chain, "eth_blockNumber", []), 16)
        rid = f"{order}-{merchant}"
        r = {"id": rid, "order": order, "merchant": merchant, "chain": chain, "chain_name": c["name"], "chain_id": c["id"],
             "token": "USDC", "token_address": c["usdc"], "to": to, "units": units, "amount": f"{units / 1e6:.6f}",
             "uri": f"ethereum:{c['usdc']}@{c['id']}/transfer?address={to}&uint256={units}",
             "from_block": max(block - 2, 0), "created": int(time.time()), "expires": int(time.time()) + EXPIRE_S, "state": "waiting"}
        with self.lock:
            self.reqs[rid] = r; self._save()
        return r

    def status(self, rid):
        with self.lock:
            r = dict(self.reqs.get(rid) or {})
        if not r:
            return None
        if r["state"] != "waiting":
            return r
        latest = int(self.rpc(r["chain"], "eth_blockNumber", []), 16)
        logs = self.rpc(r["chain"], "eth_getLogs", [{"fromBlock": hex(r["from_block"]), "toBlock": "latest", "address": r["token_address"],
                                                     "topics": [TRANSFER, None, "0x" + "0" * 24 + r["to"][2:].lower()]}])
        for lg in logs:
            if int(lg["data"], 16) == r["units"]:
                conf = latest - int(lg["blockNumber"], 16) + 1
                r.update(tx=lg["transactionHash"], confirmations=conf)
                if conf >= self.conf:
                    r.update(state="paid", paid_at=int(time.time()))
                break
        else:
            if time.time() > r["expires"]:
                r["state"] = "expired"
        with self.lock:
            self.reqs[r["id"]] = r; self._save()
        return r

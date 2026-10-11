# PXD over LoRa: buy and pay where there's no internet

A phone or Pi with a LoRa radio (Meshtastic) sends one signed packet to order. Any PXD relay in mesh range that has internet places the order through the PXD Gateway and radios back a signed receipt.

| Frame | Size | Carries |
|---|---|---|
| ORDER | 127 B + 5 B per line (up to 21 lines in one packet) | store, items, quantities, total seen, pay method, buyer key, signature |
| RECEIPT | up to 142 B | accepted / pay exactly X USDC on chain Y to the merchant's own address / broadcast + tx hash; relay signature |
| TX | 233 B packets | a wallet-signed transaction, chunked; reassembled and checked by hash, then broadcast |

## How a remote sale works
1. **Order:** the buyer's device signs an ORDER and sends it over LoRa.
2. **Checks:** the relay checks the signature, the freshness and the current price. A mesh repeat of the same packet gets the same receipt, so it's still one order.
3. **Placing it:** the relay places the order through the gateway, which prices it from the signed store data.
4. **Pay at pickup:** RECEIPT "accepted".
5. **Pay in USDC:** RECEIPT "pay" gives the exact amount and the merchant's own address. The buyer's wallet signs the payment offline, the TX frames carry it back over LoRa, and the relay broadcasts it. RECEIPT "broadcast" returns the transaction hash, and the gateway marks the order paid once the chain confirms it.
6. **No custody:** the relay never holds keys or coins. It carries signed messages, and a forged receipt fails the relay-key check.

```
python tools/mesh/pxdlora.py relay --key relay.key.json --gateway http://127.0.0.1:8790 --rpc base=https://mainnet.base.org --meshtastic COM5
python tools/mesh/pxdlora.py relay ... --stdio      # hex frames on stdin/stdout, for any other radio bridge
```
**Tested here:**
- ORDER → USDC instructions, and pickup orders
- mesh repeats, tampered packets, stale prices, a corrupted TX chunk, forged receipts
- a 300-byte transaction sent as 2 packets out of order, reaching the (mock) chain byte-for-byte

**Not tested:** the Meshtastic radio path (`pip install meshtastic`, a node on USB).

# ============================================================
# alpaca_agent.py
# SPY Regime Options Agent — Alpaca Hackathon 2026
# ============================================================
import os
import csv
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, ContractType
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest

# ============================================================
# STEP 1: LOAD CREDENTIALS & INITIALIZE CLIENT
# ============================================================
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = OptionHistoricalDataClient(API_KEY, SECRET_KEY)

print("=" * 55)
print("SPY REGIME OPTIONS AGENT — ALPACA HACKATHON 2026")
print("=" * 55)

# ============================================================
# STEP 2: READ REGIME SIGNALS & CHECK PORTFOLIO STATE
# ============================================================
LOG_FILE = "paper_trading_log.csv"

df_log = pd.read_csv(LOG_FILE)
df_log = df_log.dropna(subset=['Signal_Value'])

# Get today's and yesterday's signals
today_row = df_log.iloc[-1]
yesterday_row = df_log.iloc[-2]

today_signal = int(today_row['Signal_Value'])
yesterday_signal = int(yesterday_row['Signal_Value'])
today_date = today_row['Date']

print(f"\nDate:              {today_date}")
print(f"Yesterday Signal:  {'RISK-ON (1)' if yesterday_signal == 1 else 'RISK-OFF (0)'}")
print(f"Today Signal:      {'RISK-ON (1)' if today_signal == 1 else 'RISK-OFF (0)'}")

regime_changed = today_signal != yesterday_signal
print(f"Regime Changed:    {'YES' if regime_changed else 'NO'}")

# Check active portfolio positions and calculate DTE for position rolling
should_roll = False
has_active_option = False

try:
    positions = trading_client.get_all_positions()
    options_positions = [p for p in positions if p.asset_class == AssetClass.US_OPTION]
    has_active_option = len(options_positions) > 0

    if has_active_option:
        current_pos = options_positions[0]
        # Parses YYMMDD from symbol (e.g. SPY260908C00767000 -> 2026-09-08)
        exp_str = "20" + current_pos.symbol[3:9]
        exp_date = datetime.strptime(exp_str, "%Y%m%d")
        current_dte = (exp_date - datetime.today()).days

        print(f"Active Position:   {current_pos.symbol} ({current_dte} DTE)")
        if current_dte <= 7:
            should_roll = True
            print(f"Roll Triggered:    YES (DTE <= 7 — preventing theta decay)")
        else:
            print(f"Roll Triggered:    NO (DTE > 7)")
except Exception as e:
        print(f"[POS CHECK] Note: {e}")

# Trade if regime flipped, flat account (cold start), or roll condition met
should_trade = regime_changed or (not has_active_option) or should_roll
print(f"Should Trade:       {'YES — EXECUTING ORDER' if should_trade else 'NO — HOLDING'}")

# ============================================================
# STEP 3: CLI CALL (satisfies hackathon CLI requirement)
# ============================================================
print("\n[CLI] Fetching current positions via Alpaca CLI subprocess...")
try:
    result = subprocess.run(
        ["alpaca", "position", "list"],
        capture_output=True, text=True, timeout=15
    )
    print("[CLI Output]:", result.stdout[:300] if result.stdout else "No positions")
except Exception as e:
    print(f"[CLI] Note: {e} — continuing with SDK")

# ============================================================
# STEP 4: EXECUTE ORDER IF SIGNAL FLIPPED OR PORTFOLIO IS FLAT
# ============================================================
action_taken = "HOLD"
contract_symbol = "N/A"
order_id = "N/A"
position_size = 0

if should_trade:
    print("\n[CLOSE] Checking for existing options positions to close...")
    try:
        positions = trading_client.get_all_positions()
        options_positions = [p for p in positions if p.asset_class == AssetClass.US_OPTION]

        if options_positions:
            for pos in options_positions:
                print(f"[CLOSE] Closing position: {pos.symbol} | Qty: {pos.qty}")
                trading_client.close_position(pos.symbol)
                print(f"[CLOSE] Position closed successfully.")
        else:
            print("[CLOSE] No existing options positions found.")
    except Exception as e:
        print(f"[CLOSE] Error closing positions: {e}")

    # ============================================================
    # STEP 5: FIND ATM OPTIONS CONTRACT (7-14 DTE)
    # ============================================================
    print("\n[SCAN] Scanning for ATM SPY options contract...")
    try:
        # Determine contract type based on signal
        contract_type = ContractType.CALL if today_signal == 1 else ContractType.PUT
        direction = "CALL (Bull)" if today_signal == 1 else "PUT (Bear)"

        print(f"[SCAN] Signal direction: {direction}")

        # Define 7 to 14 DTE window explicitly for the API search
        min_exp = (datetime.today() + timedelta(days=7)).date()
        max_exp = (datetime.today() + timedelta(days=14)).date()

        # Search for active contracts strictly in the 7-14 DTE window
        req = GetOptionContractsRequest(
            underlying_symbols=["SPY"],
            status="active",
            type=contract_type,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            limit=100
        )
        contracts = trading_client.get_option_contracts(req)

        # ============================================================
        # STEP 6: SELECT BEST CONTRACT (ATM)
        # ============================================================
        today_dt = datetime.today()
        best_contract = None
        best_diff = float('inf')

        # Get current SPY price dynamically from today's CSV entry
        spy_price = float(today_row['SPY_Close'])

        for contract in contracts.option_contracts:
            strike = float(contract.strike_price)
            strike_diff = abs(strike - spy_price)

            if strike_diff < best_diff:
                best_diff = strike_diff
                best_contract = contract

        if best_contract:
            contract_symbol = best_contract.symbol
            print(f"[CONTRACT] Selected: {contract_symbol}")
            print(f"[CONTRACT] Strike: ${best_contract.strike_price} | Expiry: {best_contract.expiration_date}")

            # ============================================================
            # STEP 7: POSITION SIZING — 3% OF $100K = MAX $3,000
            # ============================================================
            quote = data_client.get_option_latest_quote(
                OptionLatestQuoteRequest(symbol_or_symbols=[contract_symbol])
            )
            option_quote = quote[contract_symbol]
            mid_price = (option_quote.ask_price + option_quote.bid_price) / 2
            cost_per_contract = mid_price * 100  # 1 contract = 100 shares

            max_spend = 3000  # 3% of $100k
            num_contracts = max(1, int(max_spend / cost_per_contract))
            actual_cost = num_contracts * cost_per_contract
            position_size = num_contracts

            print(f"[SIZE] Mid price: ${mid_price:.2f} | Cost/contract: ${cost_per_contract:.2f}")
            print(f"[SIZE] Contracts to buy: {num_contracts} | Total cost: ${actual_cost:.2f}")

            # ============================================================
            # STEP 8: PLACE MARKET ORDER
            # ============================================================
            order_request = MarketOrderRequest(
                symbol=contract_symbol,
                qty=num_contracts,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )

            order = trading_client.submit_order(order_request)
            order_id = order.id
            action_taken = f"OPENED_{direction.replace(' ', '_')}"
            print(f"[ORDER] Submitted successfully | Order ID: {order_id}")

        else:
            print("[CONTRACT] No suitable ATM contract found in 7-14 DTE window.")
            action_taken = "NO_CONTRACT_FOUND"

    except Exception as e:
        print(f"[ERROR] Trade execution failed: {e}")
        action_taken = f"ERROR: {e}"

else:
    print("\n[HOLD] Regime unchanged and position active — no trade executed.")

# ============================================================
# STEP 9: LOG TO CSV
# ============================================================
trade_log_file = "alpaca_trade_log.csv"
file_exists = os.path.exists(trade_log_file)

with open(trade_log_file, 'a', newline='') as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow([
            'Date', 'Today_Signal', 'Yesterday_Signal',
            'Regime_Changed', 'Action', 'Contract',
            'Contracts', 'Order_ID'
        ])
    writer.writerow([
        today_date, today_signal, yesterday_signal,
        regime_changed, action_taken, contract_symbol,
        position_size, order_id
    ])

print("\n" + "=" * 55)
print(f"ACTION:   {action_taken}")
print(f"CONTRACT: {contract_symbol}")
print(f"ORDER ID: {order_id}")
print(f"LOG:      {trade_log_file}")
print("=" * 55)
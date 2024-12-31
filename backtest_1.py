import os
import pandas as pd

# Load the CSV file
file_path = "xauusd.csv"
if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit()

df = pd.read_csv(file_path)

# Convert 'Local time' column to datetime
try:
    df['Local time'] = pd.to_datetime(df['Local time'], format='%d.%m.%Y %H:%M:%S')
except Exception as e:
    print(f"Error parsing 'Local time' column: {e}")
    exit()

# Function to get the closing price for a specific date and time
def get_closing_price(year, month, day, hour, minute):
    # Create a timestamp for the input time
    input_time = pd.Timestamp(year, month, day, hour, minute)
    
    # Filter the dataframe for the exact time
    try:
        row = df.loc[df['Local time'] == input_time]
        if not row.empty:
            return row['Close'].iloc[0]
        else:
            print(f"No data found for the specified time: {input_time}")
            return None
    except Exception as e:
        print(f"Error fetching closing price: {e}")
        return None

# Function to format runtime
def format_runtime(runtime):
    days = runtime.days
    hours, remainder = divmod(runtime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    formatted_runtime = ""
    if days > 0:
        formatted_runtime += f"{days}D "
    if hours > 0:
        formatted_runtime += f"{hours}H "
    if minutes > 0:
        formatted_runtime += f"{minutes}Min"
    return formatted_runtime.strip()

# Function to calculate pips
def calculate_pips(entry_price, target_price):
    return abs(target_price - entry_price) * 10

# Function to validate trade inputs
def validate_trade_inputs(entry_price, stoploss_price, takeprofit_price, trade_type):
    if trade_type.lower() == 'buy':
        if stoploss_price >= entry_price:
            print("Invalid input: For a Buy trade, SL should be below the entry price.")
            return False
        if takeprofit_price <= entry_price:
            print("Invalid input: For a Buy trade, TP should be above the entry price.")
            return False
    elif trade_type.lower() == 'sell':
        if stoploss_price <= entry_price:
            print("Invalid input: For a Sell trade, SL should be above the entry price.")
            return False
        if takeprofit_price >= entry_price:
            print("Invalid input: For a Sell trade, TP should be below the entry price.")
            return False
    else:
        print("Invalid trade type. Please enter 'Buy' or 'Sell'.")
        return False
    return True

# Function to monitor trade and check SL/TP conditions
def monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type, tolerance=0.1):
    # Get the entry price based on input time (only using Close price)
    entry_price = get_closing_price(entry_time.year, entry_time.month, entry_time.day, entry_time.hour, entry_time.minute)
    if entry_price is None:
        return

    # Validate trade inputs
    if not validate_trade_inputs(entry_price, stoploss_price, takeprofit_price, trade_type):
        return

    # Print entry details
    print("Pair: XAUUSD")
    print(f"Trade Type: {trade_type.capitalize()}")
    print(f"Entry Price: {entry_price:.3f} | Time: {entry_time.strftime('%I:%M %p (%d %B %Y)')}")
    print(f"SL Price: {stoploss_price:.3f} ({calculate_pips(entry_price, stoploss_price):.2f} pips) | TP Price: {takeprofit_price:.3f} ({calculate_pips(entry_price, takeprofit_price):.2f} pips)")

    # Filter the DataFrame for rows after the entry time
    df_filtered = df[df['Local time'] > entry_time]
    if df_filtered.empty:
        print("No data available after the specified entry time.")
        return

    # Calculate SL and TP pips
    sl_pips = calculate_pips(entry_price, stoploss_price)
    tp_pips = calculate_pips(entry_price, takeprofit_price)

    # Iterate through rows after the entry time
    for _, row in df_filtered.iterrows():
        current_high = row['High']
        current_low = row['Low']
        current_time = row['Local time']

        # Logic for Buy
        if trade_type.lower() == 'buy':
            # Check if High exceeds TP or Low goes below SL for Buy
            if current_high >= takeprofit_price - tolerance:  # TP for Buy
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                print(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                print(f"PnL: {rr:.2f}R\n")
                break
            elif current_low <= stoploss_price + tolerance:  # SL for Buy
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                print(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                print(f"PnL: -1R\n")
                break

        # Logic for Sell
        elif trade_type.lower() == 'sell':
            # Check if Low exceeds TP or High goes above SL for Sell
            if current_low <= takeprofit_price + tolerance:  # TP for Sell
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                print(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                print(f"PnL: {rr:.2f}R\n")
                break
            elif current_high >= stoploss_price - tolerance:  # SL for Sell
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                print(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                print(f"PnL: -1R\n")
                break

    # Monitor for 3R or breakeven independently
    three_r_pips = 3 * sl_pips
    three_r_target = entry_price + three_r_pips / 10 if trade_type.lower() == 'buy' else entry_price - three_r_pips / 10
    breakeven_triggered = False
    print("(3R System)")

    for _, row in df_filtered.iterrows():
        current_high = row['High']
        current_low = row['Low']
        current_time = row['Local time']

        # Logic for Buy
        if trade_type.lower() == 'buy':
            if not breakeven_triggered and current_high >= entry_price + sl_pips / 10 - tolerance:
                breakeven_triggered = True
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                print(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
            if breakeven_triggered and current_low <= entry_price + tolerance:
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                print(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                return
            if current_high >= three_r_target - tolerance:
                three_r_runtime = current_time - entry_time
                formatted_three_r_runtime = format_runtime(three_r_runtime)
                three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                print(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                return

        # Logic for Sell
        elif trade_type.lower() == 'sell':
            if not breakeven_triggered and current_low <= entry_price - sl_pips / 10 + tolerance:
                breakeven_triggered = True
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                print(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
            if breakeven_triggered and current_high >= entry_price - tolerance:
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                print(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                return
            if current_low <= three_r_target + tolerance:
                three_r_runtime = current_time - entry_time
                formatted_three_r_runtime = format_runtime(three_r_runtime)
                three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                print(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                return

    # If no SL/TP is hit
    last_time = df_filtered['Local time'].iloc[-1]
    last_price = df_filtered['Close'].iloc[-1]
    print(f"No SL/TP hit. Last price checked: {last_price:.3f} at {last_time.strftime('%I:%M %p (%d %B %Y)')}.")

# Input system to get trade details
def input_trade_details():
    try:
        # Input entry time
        year = int(input("Enter year: "))
        month = int(input("Enter month: "))
        day = int(input("Enter day: "))
        hour = int(input("Enter hour (24-hour format): "))
        minute = int(input("Enter minute: "))
        entry_time = pd.Timestamp(year, month, day, hour, minute)

        # Input trade type
        trade_type = input("Enter trade type (Buy/Sell): ").strip().lower()
        if trade_type not in ['buy', 'sell']:
            print("Invalid trade type. Please enter 'Buy' or 'Sell'.")
            return None, None, None, None

        # Input stoploss and take profit prices
        stoploss_price = float(input("Enter the stop loss price: "))
        takeprofit_price = float(input("Enter the take profit price: "))

        return entry_time, stoploss_price, takeprofit_price, trade_type

    except ValueError as ve:
        print(f"Invalid input: {ve}")
        return None, None, None, None

# Main Execution
entry_time, stoploss_price, takeprofit_price, trade_type = input_trade_details()
if entry_time and stoploss_price and takeprofit_price and trade_type:
    print()
    monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type)

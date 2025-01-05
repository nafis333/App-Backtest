from flask import Flask, render_template, request
import os
import pandas as pd
from calendar import monthrange
import traceback

app = Flask(__name__)

# Function to find the first .parquet file containing "xauusd" in its name (case-insensitive)
def find_xauusd_parquet_file():
    files_in_directory = os.listdir()
    for file_name in files_in_directory:
        if "xauusd" in file_name.lower() and file_name.lower().endswith(".parquet"):
            return file_name
    return None

# Find the .parquet file
file_path = find_xauusd_parquet_file()
if not file_path:
    raise FileNotFoundError("No .parquet file containing 'xauusd' found in the current directory.")

# Load the .parquet file
df = pd.read_parquet(file_path)

# Convert 'Local time' column to datetime
try:
    df['Local time'] = pd.to_datetime(df['Local time'], format='%d.%m.%Y %H:%M:%S')
except Exception as e:
    raise ValueError(f"Error parsing 'Local time' column: {e}")

# Drop rows with NaN values in the 'Open', 'High', 'Low', 'Close' columns
df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])

# Function to get the closing price for a specific date and time
def get_closing_price(year, month, day, hour, minute):
    input_time = pd.Timestamp(year, month, day, hour, minute)
    try:
        row = df.loc[df['Local time'] == input_time]
        if not row.empty:
            return row['Close'].iloc[0]
        else:
            return None
    except Exception as e:
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
            return "Invalid input: For a Buy trade, SL should be below the entry price."
        if takeprofit_price <= entry_price:
            return "Invalid input: For a Buy trade, TP should be above the entry price."
    elif trade_type.lower() == 'sell':
        if stoploss_price <= entry_price:
            return "Invalid input: For a Sell trade, SL should be above the entry price."
        if takeprofit_price >= entry_price:
            return "Invalid input: For a Sell trade, TP should be below the entry price."
    else:
        return "Invalid trade type. Please enter 'Buy' or 'Sell'."
    return None

# Function to monitor trade and check SL/TP conditions
def monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type, breakeven):
    entry_price = get_closing_price(entry_time.year, entry_time.month, entry_time.day, entry_time.hour, entry_time.minute)
    if entry_price is None:
        return ["No data found for the specified entry time. Possible reasons: incorrect date/time or missing data in the CSV file."]

    validation_error = validate_trade_inputs(entry_price, stoploss_price, takeprofit_price, trade_type)
    if validation_error:
        return [validation_error]

    results = []
    results.append(f"Pair: XAUUSD")
    results.append(f"Trade Type: {trade_type.capitalize()}")
    results.append(f"Entry Price: {entry_price:.3f} | Time: {entry_time.strftime('%I:%M %p (%d %B %Y)')}")
    results.append(f"SL Price: {stoploss_price:.3f} ({calculate_pips(entry_price, stoploss_price):.2f} pips) | TP Price: {takeprofit_price:.3f} ({calculate_pips(entry_price, takeprofit_price):.2f} pips)")

    df_filtered = df[df['Local time'] > entry_time]
    if df_filtered.empty:
        return ["No data available after the specified entry time."]

    sl_pips = calculate_pips(entry_price, stoploss_price)
    tp_pips = calculate_pips(entry_price, takeprofit_price)

    for _, row in df_filtered.iterrows():
        current_high = row['High']
        current_low = row['Low']
        current_time = row['Local time']

        if trade_type.lower() == 'buy':
            if current_high >= takeprofit_price - 0.1:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                results.append(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: {rr:.2f}R\n")
                break
            elif current_low <= stoploss_price + 0.1:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: -1R\n")
                break

        elif trade_type.lower() == 'sell':
            if current_low <= takeprofit_price + 0.1:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                results.append(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: {rr:.2f}R\n")
                break
            elif current_high >= stoploss_price - 0.1:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: -1R\n")
                break

    if breakeven:
        three_r_pips = 3 * sl_pips
        three_r_target = entry_price + three_r_pips / 10 if trade_type.lower() == 'buy' else entry_price - three_r_pips / 10
        breakeven_triggered = False
        results.append("(3R System)")
        results.append(f"3R TP: {three_r_target:.3f} ({three_r_pips:.2f} pips)")

        for _, row in df_filtered.iterrows():
            current_high = row['High']
            current_low = row['Low']
            current_time = row['Local time']

            if trade_type.lower() == 'buy':
                # Check if SL is hit before breakeven
                if current_low <= stoploss_price + 0.1:
                    runtime = current_time - entry_time
                    formatted_runtime = format_runtime(runtime)
                    sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                    results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                    results.append(f"PnL: -1R\n")
                    return results

                # Check breakeven trigger
                if not breakeven_triggered and current_high >= entry_price + sl_pips / 10 - 0.1:
                    breakeven_triggered = True
                    breakeven_runtime = current_time - entry_time
                    formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                    results.append(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")

                # Check breakeven hit
                if breakeven_triggered and current_low <= entry_price + 0.1:
                    breakeven_runtime = current_time - entry_time
                    formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                    results.append(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                    return results

                # Check 3R target hit
                if current_high >= three_r_target - 0.1:
                    three_r_runtime = current_time - entry_time
                    formatted_three_r_runtime = format_runtime(three_r_runtime)
                    three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                    results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                    return results

            elif trade_type.lower() == 'sell':
                # Check if SL is hit before breakeven
                if current_high >= stoploss_price - 0.1:
                    runtime = current_time - entry_time
                    formatted_runtime = format_runtime(runtime)
                    sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                    results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                    results.append(f"PnL: -1R\n")
                    return results

                # Check breakeven trigger
                if not breakeven_triggered and current_low <= entry_price - sl_pips / 10 + 0.1:
                    breakeven_triggered = True
                    breakeven_runtime = current_time - entry_time
                    formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                    results.append(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")

                # Check breakeven hit
                if breakeven_triggered and current_high >= entry_price - 0.1:
                    breakeven_runtime = current_time - entry_time
                    formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                    results.append(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                    return results

                # Check 3R target hit
                if current_low <= three_r_target + 0.1:
                    three_r_runtime = current_time - entry_time
                    formatted_three_r_runtime = format_runtime(three_r_runtime)
                    three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                    results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                    return results
                
    else:
        # Logic for when breakeven is False, but still use the 3R System
        results.append("( 3R System (Without Breakeven) )")

        # Calculate the 3R target
        three_r_pips = 3 * sl_pips
        three_r_target = entry_price + three_r_pips / 10 if trade_type.lower() == 'buy' else entry_price - three_r_pips / 10
        results.append(f"3R TP: {three_r_target:.3f} ({three_r_pips:.2f} pips)")

        for _, row in df_filtered.iterrows():
            current_high = row['High']
            current_low = row['Low']
            current_time = row['Local time']

            if trade_type.lower() == 'buy':
                # Check if SL is hit before 3R
                if current_low <= stoploss_price + 0.1:
                    runtime = current_time - entry_time
                    formatted_runtime = format_runtime(runtime)
                    sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                    results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                    results.append(f"PnL: -1R\n")
                    return results

                # Check if 3R target is hit
                if current_high >= three_r_target - 0.1:
                    three_r_runtime = current_time - entry_time
                    formatted_three_r_runtime = format_runtime(three_r_runtime)
                    three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                    results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                    return results

            elif trade_type.lower() == 'sell':
                # Check if SL is hit before 3R
                if current_high >= stoploss_price - 0.1:
                    runtime = current_time - entry_time
                    formatted_runtime = format_runtime(runtime)
                    sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                    results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                    results.append(f"PnL: -1R\n")
                    return results

                # Check if 3R target is hit
                if current_low <= three_r_target + 0.1:
                    three_r_runtime = current_time - entry_time
                    formatted_three_r_runtime = format_runtime(three_r_runtime)
                    three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                    results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                    return results

    return ["Neither Stoploss nor 3R Take Profit was hit within the given data range."]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/monitor_trade', methods=['POST'])
def monitor_trade_route():
    try:
        # Extract and validate input values
        year = int(request.form['year'])
        month = int(request.form['month'])
        day = int(request.form['day'])
        hour = int(request.form['hour'])
        minute = int(request.form['minute'])

        # Validate month, day, hour, minute
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12.")
        
        # Validate day according to the month
        _, days_in_month = monthrange(year, month)
        if not (1 <= day <= days_in_month):
            raise ValueError(f"Day must be between 1 and {days_in_month} for the given month.")
        
        if not (0 <= hour <= 23):
            raise ValueError("Hour must be between 0 and 23.")
        if not (0 <= minute <= 59):
            raise ValueError("Minute must be between 0 and 59.")

        entry_time = pd.Timestamp(year, month, day, hour, minute)

        # Validate trade type
        trade_type = request.form['trade_type'].strip().lower()
        if trade_type not in ['buy', 'sell']:
            raise ValueError("Trade type must be 'buy' or 'sell'.")

        # Extract input type and validate
        input_type = request.form['input_type'].strip().lower()
        if input_type not in ['prices', 'pips']:
            raise ValueError("Input type must be 'prices' or 'pips'.")

        # Get the entry price for the given entry time
        entry_price = get_closing_price(entry_time.year, entry_time.month, entry_time.day, entry_time.hour, entry_time.minute)
        if entry_price is None:
            raise ValueError("No data found for the specified entry time.")

        # Validate and convert stoploss and takeprofit inputs based on input type
        if input_type == 'prices':
            stoploss_price = float(request.form['stoploss_price'])
            takeprofit_price = float(request.form['takeprofit_price'])
        elif input_type == 'pips':
            stoploss_pips = float(request.form['stoploss_pips'])
            takeprofit_pips = float(request.form['takeprofit_pips'])
            if trade_type == 'buy':
                stoploss_price = entry_price - stoploss_pips / 10
                takeprofit_price = entry_price + takeprofit_pips / 10
            elif trade_type == 'sell':
                stoploss_price = entry_price + stoploss_pips / 10
                takeprofit_price = entry_price - takeprofit_pips / 10
        else:
            raise ValueError("Invalid input type.")

        # Validate breakeven input
        breakeven_input = request.form['breakeven'].strip().lower()
        breakeven = breakeven_input in ['true', '1', 'yes']

        # Call the monitoring logic
        results = monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type, breakeven)

        return render_template('results.html', results=results)

    except ValueError as ve:
        # Render error back to the form with an error message
        return render_template('index.html', error=f"Invalid input: {ve}")
    except Exception as e:
        # Log unexpected errors and show a generic error page with detailed information
        error_info = traceback.format_exc()
        print(f"Unexpected error: {e}\n{error_info}")  # Replace with proper logging
        return render_template('error.html', error=f"An unexpected error occurred: {e}", error_info=error_info)

if __name__ == '__main__':
    app.run(debug=True)
    

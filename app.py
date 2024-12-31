from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# Load the CSV file
file_path = "xauusd.csv"
if not os.path.exists(file_path):
    raise FileNotFoundError(f"File not found: {file_path}")

df = pd.read_csv(file_path)

# Convert 'Local time' column to datetime
try:
    df['Local time'] = pd.to_datetime(df['Local time'], format='%d.%m.%Y %H:%M:%S')
except Exception as e:
    raise ValueError(f"Error parsing 'Local time' column: {e}")

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
def monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type, tolerance=0.1):
    entry_price = get_closing_price(entry_time.year, entry_time.month, entry_time.day, entry_time.hour, entry_time.minute)
    if entry_price is None:
        return ["No data found for the specified entry time."]

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
            if current_high >= takeprofit_price - tolerance:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                results.append(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: {rr:.2f}R\n")
                break
            elif current_low <= stoploss_price + tolerance:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: -1R\n")
                break

        elif trade_type.lower() == 'sell':
            if current_low <= takeprofit_price + tolerance:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                tp_pips_hit = calculate_pips(entry_price, takeprofit_price)
                rr = tp_pips_hit / sl_pips
                results.append(f"Take Profit hit: {takeprofit_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: {rr:.2f}R\n")
                break
            elif current_high >= stoploss_price - tolerance:
                runtime = current_time - entry_time
                formatted_runtime = format_runtime(runtime)
                sl_pips_hit = calculate_pips(entry_price, stoploss_price)
                results.append(f"Stoploss hit: {stoploss_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_runtime}")
                results.append(f"PnL: -1R\n")
                break

    three_r_pips = 3 * sl_pips
    three_r_target = entry_price + three_r_pips / 10 if trade_type.lower() == 'buy' else entry_price - three_r_pips / 10
    breakeven_triggered = False
    results.append("(3R System)")

    for _, row in df_filtered.iterrows():
        current_high = row['High']
        current_low = row['Low']
        current_time = row['Local time']

        if trade_type.lower() == 'buy':
            if not breakeven_triggered and current_high >= entry_price + sl_pips / 10 - tolerance:
                breakeven_triggered = True
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                results.append(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
            if breakeven_triggered and current_low <= entry_price + tolerance:
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                results.append(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                return results
            if current_high >= three_r_target - tolerance:
                three_r_runtime = current_time - entry_time
                formatted_three_r_runtime = format_runtime(three_r_runtime)
                three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                return results

        elif trade_type.lower() == 'sell':
            if not breakeven_triggered and current_low <= entry_price - sl_pips / 10 + tolerance:
                breakeven_triggered = True
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                results.append(f"Breakeven at: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
            if breakeven_triggered and current_high >= entry_price - tolerance:
                breakeven_runtime = current_time - entry_time
                formatted_breakeven_runtime = format_runtime(breakeven_runtime)
                results.append(f"Breakeven hit: {entry_price:.3f} | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_breakeven_runtime}")
                return results
            if current_low <= three_r_target + tolerance:
                three_r_runtime = current_time - entry_time
                formatted_three_r_runtime = format_runtime(three_r_runtime)
                three_r_pips_hit = calculate_pips(entry_price, three_r_target)
                results.append(f"3R hit: {three_r_target:.3f} ({three_r_pips_hit:.2f} pips) | Time: {current_time.strftime('%I:%M %p (%d %B %Y)')} | Runtime: {formatted_three_r_runtime}")
                return results

    last_time = df_filtered['Local time'].iloc[-1]
    last_price = df_filtered['Close'].iloc[-1]
    results.append(f"No SL/TP hit. Last price checked: {last_price:.3f} at {last_time.strftime('%I:%M %p (%d %B %Y)')}.")
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/monitor_trade', methods=['POST'])
def monitor_trade_route():
    try:
        year = int(request.form['year'])
        month = int(request.form['month'])
        day = int(request.form['day'])
        hour = int(request.form['hour'])
        minute = int(request.form['minute'])
        entry_time = pd.Timestamp(year, month, day, hour, minute)

        trade_type = request.form['trade_type'].strip().lower()
        stoploss_price = float(request.form['stoploss_price'])
        takeprofit_price = float(request.form['takeprofit_price'])

        results = monitor_trade(entry_time, stoploss_price, takeprofit_price, trade_type)
        return render_template('results.html', results=results)
    except ValueError as ve:
        return f"Invalid input: {ve}"

if __name__ == '__main__':
    app.run(debug=True)

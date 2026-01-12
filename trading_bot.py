import logging
import argparse
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from config import API_KEY, API_SECRET
from decimal import Decimal, ROUND_UP, getcontext

# pip install python-binance
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ============================================
# 1. LOGGING SETUP (Requirement: Log API requests)
# ============================================
def setup_logging():
    """Configures logging to file and console."""
    logger = logging.getLogger('TradingBot')
    logger.setLevel(logging.INFO)

    # Prevent duplicate logs if function is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Format for logs
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler (logs everything)
    file_handler = logging.FileHandler('bot_execution.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler (prints to terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Enable verbose HTTP logging from python-binance library
    logging.getLogger('binance.base_client').setLevel(logging.INFO)

    return logger

# Initialize logger
logger = setup_logging()

# ============================================
# 2. DATA CLASS FOR ORDER RESULTS
# ============================================
@dataclass
class OrderResult:
    """Structured output for order placement results."""
    success: bool
    order_id: Optional[int] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

# ============================================
# 3. MAIN TRADING BOT CLASS
# ============================================
class BasicBot:
    """
    A simplified trading bot for Binance Futures Testnet.
    Places MARKET and LIMIT orders for USDT-M pairs.
    """
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initializes the Binance client for Testnet[citation:1][citation:7].

        Args:
            api_key (str): Your API key from Binance Testnet.
            api_secret (str): Your API secret from Binance Testnet.
            testnet (bool): If True, uses the testnet environment.
        """
        try:
            if testnet:
                # Explicitly use the Futures Testnet URL[citation:5]
                self.client = Client(
                    api_key,
                    api_secret,
                    testnet=True,
                    requests_params={'timeout': 10}
                )
                # Override the base URL to the specific Futures Testnet
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com'
                logger.info("Client initialized for Binance Futures TESTNET.")
            else:
                self.client = Client(api_key, api_secret)
                logger.info("Client initialized for Binance Futures MAINNET.")

            # Test connection
            self.client.futures_ping()
            logger.info("Connection to Binance API successful.")

        except BinanceAPIException as e:
            logger.error(f"Binance API Error during init: {e.status_code} - {e.message}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    # ------------------------------------------------------
    # CORE FUNCTION: PLACE MARKET ORDER
    # ------------------------------------------------------
    def place_market_order(self, symbol: str, side: str, quantity: float, auto_adjust: bool = False) -> OrderResult:
        """
        Places a MARKET order on Binance Futures.

        Args:
            symbol (str): Trading pair, e.g., 'BTCUSDT'.
            side (str): 'BUY' or 'SELL'.
            quantity (float): Order quantity.

        Returns:
            OrderResult: Structured result of the order attempt.
        """
        logger.info(f"Attempting MARKET order: {side} {quantity} of {symbol}")
        try:
            # Input validation
            if side.upper() not in ['BUY', 'SELL']:
                return OrderResult(success=False, message="Invalid side. Use 'BUY' or 'SELL'.")
            # Enforce minimum notional requirement for this symbol
            try:
                # increase decimal precision for safety
                getcontext().prec = 18
                price = Decimal(self.client.futures_symbol_ticker(symbol=symbol.upper())['price'])

                # fetch symbol filters
                info = self.client.futures_exchange_info()
                sym = next(s for s in info['symbols'] if s['symbol'] == symbol.upper())
                filters = {f['filterType']: f for f in sym.get('filters', [])}

                # attempt to read minimum notional
                min_notional_str = (
                    filters.get('MIN_NOTIONAL', {}).get('minNotional')
                    or filters.get('NOTIONAL', {}).get('minNotional')
                    or filters.get('MIN_NOTIONAL', {}).get('notional')
                )

                if min_notional_str:
                    min_notional = Decimal(min_notional_str)
                    step_size = Decimal(filters['LOT_SIZE']['stepSize'])
                    required_qty = (min_notional / price)
                    multiplier = (required_qty / step_size).to_integral_value(rounding=ROUND_UP)
                    min_qty = multiplier * step_size
                    if Decimal(str(quantity)) < min_qty:
                        if auto_adjust:
                            adjusted_qty = float(min_qty)
                            logger.info(f"Auto-adjusting quantity {quantity} -> {adjusted_qty} to meet min notional {min_notional}")
                            quantity = adjusted_qty
                        else:
                            return OrderResult(success=False, message=f"Quantity too small. Minimum quantity for {symbol} is {min_qty} (min notional {min_notional}).")
            except Exception:
                # if any of the checks fail, continue and let the API return a meaningful error
                logger.debug("Could not validate min_notional for symbol; proceeding to place order")

            # Place the order
            order = self.client.futures_create_order(
                symbol=symbol.upper(),
                side=side.upper(),
                type='MARKET',
                quantity=quantity
            )
            logger.info(f"Order placed successfully. Response: {order}")

            return OrderResult(
                success=True,
                order_id=order['orderId'],
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity,
                status=order['status'],
                message="Market order placed successfully."
            )

        except BinanceAPIException as e:
            error_msg = f"API Error: {e.status_code} - {e.message}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg, message="Order failed due to API error.")
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg, message="Order failed due to an unexpected error.")

    # ------------------------------------------------------
    # CORE FUNCTION: PLACE LIMIT ORDER
    # ------------------------------------------------------
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        """
        Places a LIMIT order on Binance Futures.

        Args:
            symbol (str): Trading pair, e.g., 'BTCUSDT'.
            side (str): 'BUY' or 'SELL'.
            quantity (float): Order quantity.
            price (float): Limit price.

        Returns:
            OrderResult: Structured result of the order attempt.
        """
        logger.info(f"Attempting LIMIT order: {side} {quantity} of {symbol} @ {price}")
        try:
            if side.upper() not in ['BUY', 'SELL']:
                return OrderResult(success=False, message="Invalid side. Use 'BUY' or 'SELL'.")

            order = self.client.futures_create_order(
                symbol=symbol.upper(),
                side=side.upper(),
                type='LIMIT',
                timeInForce='GTC',  # Good-Til-Cancelled
                quantity=quantity,
                price=price
            )
            logger.info(f"Order placed successfully. Response: {order}")

            return OrderResult(
                success=True,
                order_id=order['orderId'],
                symbol=symbol,
                side=side,
                order_type='LIMIT',
                quantity=quantity,
                price=price,
                status=order['status'],
                message="Limit order placed successfully."
            )

        except BinanceAPIException as e:
            error_msg = f"API Error: {e.status_code} - {e.message}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg, message="Order failed due to API error.")
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg, message="Order failed due to an unexpected error.")

    # ------------------------------------------------------
    # BONUS FUNCTION: PLACE STOP-LIMIT ORDER
    # ------------------------------------------------------
    def place_stop_limit_order(self, symbol: str, side: str, quantity: float, price: float, stop_price: float) -> OrderResult:
        """
        (BONUS) Places a STOP-LIMIT order.
        The STOP price triggers the order, which is then executed as a LIMIT order at the specified price.
        """
        logger.info(f"Attempting STOP-LIMIT order: {side} {quantity} of {symbol}, Stop@{stop_price}, Limit@{price}")
        try:
            # Note: The 'type' for a Stop-Limit order in Binance Futures is 'STOP'
            order = self.client.futures_create_order(
                symbol=symbol.upper(),
                side=side.upper(),
                type='STOP',
                quantity=quantity,
                price=price,          # The limit price
                stopPrice=stop_price, # The trigger price
                timeInForce='GTC'
            )
            logger.info(f"Stop-Limit order placed. Response: {order}")
            return OrderResult(
                success=True,
                order_id=order['orderId'],
                symbol=symbol,
                side=side,
                order_type='STOP_LIMIT',
                quantity=quantity,
                price=price,
                status=order['status'],
                message="Stop-Limit order placed successfully."
            )
        except BinanceAPIException as e:
            error_msg = f"API Error on Stop-Limit: {e.status_code} - {e.message}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error on Stop-Limit: {e}"
            logger.error(error_msg)
            return OrderResult(success=False, error=error_msg)

# ============================================
# 4. COMMAND-LINE INTERFACE (CLI) HANDLER
# ============================================
def parse_arguments():
    """Parses and validates user input from the command line."""
    parser = argparse.ArgumentParser(description='Binance Futures Testnet Trading Bot')
    parser.add_argument('--symbol', required=True, help='Trading pair (e.g., BTCUSDT)')
    parser.add_argument('--side', required=True, choices=['BUY', 'SELL'], help='Order side')
    parser.add_argument('--type', required=True, choices=['MARKET', 'LIMIT', 'STOP_LIMIT'], help='Order type')
    parser.add_argument('--quantity', required=True, type=float, help='Order quantity')
    parser.add_argument('--price', type=float, help='Limit/Stop price (REQUIRED for LIMIT and STOP_LIMIT)')
    parser.add_argument('--stop-price', type=float, help='Stop price (REQUIRED for STOP_LIMIT)')
    parser.add_argument('--auto-adjust', action='store_true', help='Automatically increase quantity to meet minimum notional')

    args = parser.parse_args()

    # Validation logic
    if args.type in ['LIMIT', 'STOP_LIMIT'] and args.price is None:
        parser.error(f"--price is required for order type {args.type}")
    if args.type == 'STOP_LIMIT' and args.stop_price is None:
        parser.error("--stop-price is required for order type STOP_LIMIT")

    return args

def print_order_result(result: OrderResult):
    """Prints a formatted summary of the order result to the console."""
    print("\n" + "="*50)
    print("ORDER EXECUTION RESULT")
    print("="*50)
    if result.success:
        print(f"✅ SUCCESS: {result.message}")
        print(f"   Order ID: {result.order_id}")
        print(f"   Symbol: {result.symbol}")
        print(f"   Side: {result.side}")
        print(f"   Type: {result.order_type}")
        print(f"   Quantity: {result.quantity}")
        if result.price:
            print(f"   Price: {result.price}")
        print(f"   Status: {result.status}")
    else:
        print(f"❌ FAILED: {result.message}")
        if result.error:
            print(f"   Error Details: {result.error}")
    print("="*50 + "\n")

# ============================================
# 5. MAIN EXECUTION BLOCK
# ============================================
if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting Binance Futures Testnet Trading Bot")
    logger.info("="*60)

    # !!! SECURITY WARNING !!!
    # NEVER hardcode live keys. Use environment variables or a config file.
    # Prefer environment variables; fall back to values from `config.py` if present.
    API_KEY = os.getenv("BINANCE_TESTNET_API_KEY") or API_KEY
    API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET") or API_SECRET

    # Trim whitespace if keys were provided via file or env
    if API_KEY:
        API_KEY = API_KEY.strip()
    if API_SECRET:
        API_SECRET = API_SECRET.strip()

    # Recommended method: Set environment variables when possible:
    # On PowerShell: $env:BINANCE_TESTNET_API_KEY = "r0NojuQt7mh..."
    # On Windows CMD: set BINANCE_TESTNET_API_KEY="r0NojuQt7mh..."

    # 1. Parse user input from CLI
    args = parse_arguments()

    # 2. Initialize the bot
    try:
        bot = BasicBot(api_key=API_KEY, api_secret=API_SECRET, testnet=True)
    except Exception as e:
        logger.critical(f"Bot initialization failed. Exiting. Error: {e}")
        print("❌ Failed to initialize bot. Check logs for details.")
        exit(1)

    # 3. Execute the requested order
    result = None
    if args.type == 'MARKET':
        result = bot.place_market_order(args.symbol, args.side, args.quantity, auto_adjust=args.auto_adjust)
    elif args.type == 'LIMIT':
        result = bot.place_limit_order(args.symbol, args.side, args.quantity, args.price)
    elif args.type == 'STOP_LIMIT':
        result = bot.place_stop_limit_order(args.symbol, args.side, args.quantity, args.price, args.stop_price)

    # 4. Output the result
    if result:
        print_order_result(result)
        # Also log the final outcome
        log_level = logging.INFO if result.success else logging.ERROR
        logger.log(log_level, f"Final order outcome: {result.message}")
    else:
        logger.error("Order execution logic failed to return a result.")

    logger.info("Trading Bot session ended.\n")
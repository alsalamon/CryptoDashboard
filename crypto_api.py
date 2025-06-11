"""
CoinGecko API integration module for cryptocurrency data
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

class CoinGeckoAPI:
    """
    Handles all interactions with CoinGecko API
    """
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()
        # Set headers to identify the application
        self.session.headers.update({
            'User-Agent': 'CryptoWidget/1.0',
            'Accept': 'application/json'
        })
        self.last_request_time = 0
        self.min_request_interval = 1.1  # Minimum 1.1 seconds between requests
    
    def _rate_limit_delay(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request_with_retry(self, url: str, params: dict = None, max_retries: int = 3) -> dict:
        """Make a request with retry logic and rate limiting"""
        if params is None:
            params = {}
            
        for attempt in range(max_retries):
            try:
                self._rate_limit_delay()
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code == 429:  # Too Many Requests
                    wait_time = 2 ** attempt * 5  # Exponential backoff: 5, 10, 20 seconds
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Request failed after {max_retries} attempts: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("Max retries exceeded")
        
    def get_supported_coins(self) -> List[Dict]:
        """
        Get list of supported cryptocurrencies
        Returns top coins by market cap
        """
        try:
            # Get top coins by market cap using markets endpoint which includes volume
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 20,  # Reduced to avoid rate limits
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            
            data = self._make_request_with_retry(url, params)
            return [{'id': coin['id'], 'name': coin['name'], 'symbol': coin['symbol'].upper()} 
                   for coin in data]
                   
        except Exception as e:
            raise Exception(f"Failed to fetch supported coins: {str(e)}")
    
    def get_current_prices(self, coin_ids: List[str]) -> Dict:
        """
        Get current prices for specified coins using markets endpoint for better volume data
        """
        if not coin_ids:
            return {}
            
        try:
            # Use markets endpoint which provides reliable volume data
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ','.join(coin_ids),
                'order': 'market_cap_desc',
                'per_page': len(coin_ids),
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            
            market_data = self._make_request_with_retry(url, params)
            
            # Convert markets response to expected format
            result = {}
            for coin in market_data:
                coin_id = coin['id']
                result[coin_id] = {
                    'usd': coin['current_price'],
                    'usd_24h_change': coin.get('price_change_percentage_24h', 0),
                    'usd_24h_vol': coin.get('total_volume', 0),
                    'usd_market_cap': coin.get('market_cap', 0),
                    'last_updated_at': coin.get('last_updated', '')
                }
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to fetch current prices: {str(e)}")
    
    def get_trading_pairs(self) -> Dict:
        """
        Get trading pair information for ETH/BTC, BTC/ETH, and EUR/USD
        """
        try:
            # Get BTC and ETH prices in USD to calculate ratios
            crypto_url = f"{self.base_url}/simple/price"
            crypto_params = {
                'ids': 'bitcoin,ethereum',
                'vs_currencies': 'usd',
                'include_24hr_change': True
            }
            
            crypto_data = self._make_request_with_retry(crypto_url, crypto_params)
            
            # Calculate trading pairs
            trading_pairs = {}
            
            if 'bitcoin' in crypto_data and 'ethereum' in crypto_data:
                btc_price_usd = crypto_data['bitcoin']['usd']
                eth_price_usd = crypto_data['ethereum']['usd']
                btc_change_24h = crypto_data['bitcoin'].get('usd_24h_change', 0)
                eth_change_24h = crypto_data['ethereum'].get('usd_24h_change', 0)
                
                if btc_price_usd > 0 and eth_price_usd > 0:
                    # ETH/BTC pair - how much ETH is worth in BTC
                    eth_btc_rate = eth_price_usd / btc_price_usd
                    trading_pairs['ETH/BTC'] = {
                        'price': eth_btc_rate,
                        'change_24h': eth_change_24h - btc_change_24h,  # Approximate relative change
                        'base': 'Ethereum',
                        'quote': 'Bitcoin'
                    }
                    
                    # BTC/ETH pair - how much BTC is worth in ETH
                    btc_eth_rate = btc_price_usd / eth_price_usd
                    trading_pairs['BTC/ETH'] = {
                        'price': btc_eth_rate,
                        'change_24h': btc_change_24h - eth_change_24h,  # Approximate relative change
                        'base': 'Bitcoin',
                        'quote': 'Ethereum'
                    }
            
            # Get EUR/USD rate using a simple approach
            try:
                # Try to get EUR price in USD using exchange rates
                exchange_url = f"{self.base_url}/exchange_rates"
                exchange_data = self._make_request_with_retry(exchange_url)
                
                if 'rates' in exchange_data and 'eur' in exchange_data['rates']:
                    usd_eur_rate = exchange_data['rates']['eur']['value']
                    if usd_eur_rate > 0:
                        eur_usd_rate = 1 / usd_eur_rate
                        trading_pairs['EUR/USD'] = {
                            'price': eur_usd_rate,
                            'change_24h': 0,  # Exchange rates don't have 24h change
                            'base': 'Euro',
                            'quote': 'US Dollar'
                        }
                else:
                    # Fallback: use approximate EUR/USD rate
                    trading_pairs['EUR/USD'] = {
                        'price': 1.08,  # Approximate EUR/USD rate
                        'change_24h': 0,
                        'base': 'Euro',
                        'quote': 'US Dollar'
                    }
            except Exception:
                # Fallback for EUR/USD if exchange rates fail
                trading_pairs['EUR/USD'] = {
                    'price': 1.08,  # Approximate EUR/USD rate
                    'change_24h': 0,
                    'base': 'Euro',
                    'quote': 'US Dollar'
                }
            
            return trading_pairs
            
        except Exception as e:
            raise Exception(f"Failed to fetch trading pairs: {str(e)}")
    
    def get_pair_historical_data(self, pair_name: str, days: int = 7) -> Tuple[List[datetime], List[float]]:
        """
        Get historical data for trading pairs
        """
        try:
            if pair_name == 'ETH/BTC':
                # Get ETH price in BTC
                return self._get_crypto_pair_history('ethereum', 'btc', days)
            elif pair_name == 'BTC/ETH':
                # Get BTC price in ETH  
                return self._get_crypto_pair_history('bitcoin', 'eth', days)
            elif pair_name == 'EUR/USD':
                # For EUR/USD, we'll use EUR price in USD and invert
                return self._get_fiat_pair_history('eur', days)
            else:
                raise ValueError(f"Unsupported trading pair: {pair_name}")
                
        except Exception as e:
            raise Exception(f"Failed to fetch historical data for {pair_name}: {str(e)}")
    
    def _get_crypto_pair_history(self, base_coin: str, quote_currency: str, days: int) -> Tuple[List[datetime], List[float]]:
        """Get historical data for crypto pairs"""
        url = f"{self.base_url}/coins/{base_coin}/market_chart"
        params = {
            'vs_currency': quote_currency,
            'days': days,
            'interval': 'hourly' if days <= 7 else 'daily'
        }
        
        response = self.session.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'prices' not in data:
            raise ValueError("No price data found in response")
        
        prices_data = data['prices']
        timestamps = [datetime.fromtimestamp(item[0] / 1000) for item in prices_data]
        prices = [item[1] for item in prices_data]
        
        return timestamps, prices
    
    def _get_fiat_pair_history(self, currency: str, days: int) -> Tuple[List[datetime], List[float]]:
        """Get historical data for fiat pairs using Bitcoin as proxy"""
        # Since CoinGecko doesn't provide direct forex historical data,
        # we'll use a workaround by getting EUR prices through Bitcoin
        try:
            url = f"{self.base_url}/coins/bitcoin/market_chart"
            params = {
                'vs_currency': currency,
                'days': days,
                'interval': 'hourly' if days <= 7 else 'daily'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if 'prices' not in data:
                # Fallback: return current EUR/USD rate as flat line
                current_rate = 1.08  # Approximate EUR/USD rate
                now = datetime.now()
                timestamps = [now - timedelta(hours=i) for i in range(24 * days, 0, -1)]
                prices = [current_rate] * len(timestamps)
                return timestamps, prices
            
            # For EUR/USD, we need to calculate based on USD/EUR data
            prices_data = data['prices']
            timestamps = [datetime.fromtimestamp(item[0] / 1000) for item in prices_data]
            
            # Get corresponding USD prices for the same timestamps
            usd_url = f"{self.base_url}/coins/bitcoin/market_chart"
            usd_params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'hourly' if days <= 7 else 'daily'
            }
            
            usd_response = self.session.get(usd_url, params=usd_params, timeout=15)
            usd_response.raise_for_status()
            usd_data = usd_response.json()
            
            if 'prices' in usd_data:
                usd_prices = [item[1] for item in usd_data['prices']]
                eur_prices = [item[1] for item in prices_data]
                
                # Calculate EUR/USD rate: (BTC/USD) / (BTC/EUR) = EUR/USD
                eur_usd_rates = []
                for i in range(min(len(usd_prices), len(eur_prices))):
                    if eur_prices[i] > 0:
                        eur_usd_rates.append(usd_prices[i] / eur_prices[i])
                    else:
                        eur_usd_rates.append(1.08)  # Fallback rate
                
                return timestamps[:len(eur_usd_rates)], eur_usd_rates
            
            # Final fallback
            current_rate = 1.08
            return timestamps, [current_rate] * len(timestamps)
            
        except Exception:
            # Ultimate fallback: return approximate flat rate
            current_rate = 1.08
            now = datetime.now()
            timestamps = [now - timedelta(hours=i) for i in range(24 * days, 0, -1)]
            prices = [current_rate] * len(timestamps)
            return timestamps, prices
    
    def get_historical_data(self, coin_id: str, days: int = 7) -> Tuple[List[datetime], List[float]]:
        """
        Get historical price data for a specific coin
        Returns timestamps and prices for the last 'days' period
        """
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'hourly' if days <= 7 else 'daily'
            }
            
            data = self._make_request_with_retry(url, params)
            
            if 'prices' not in data:
                raise ValueError("No price data found in response")
            
            # Extract timestamps and prices
            prices_data = data['prices']
            timestamps = [datetime.fromtimestamp(item[0] / 1000) for item in prices_data]
            prices = [item[1] for item in prices_data]
            
            return timestamps, prices
            
        except Exception as e:
            raise Exception(f"Failed to fetch historical data for {coin_id}: {str(e)}")
    
    def get_coin_info(self, coin_id: str) -> Dict:
        """
        Get detailed information about a specific coin
        """
        try:
            url = f"{self.base_url}/coins/{coin_id}"
            params = {
                'localization': False,
                'tickers': False,
                'market_data': True,
                'community_data': False,
                'developer_data': False,
                'sparkline': False
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch coin info for {coin_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing coin info: {str(e)}")

def format_price(price: float, currency: str = 'USD') -> str:
    """
    Format price with appropriate decimal places and currency
    """
    if currency == 'USD':
        if price >= 1000:
            return f"${price:,.2f}"
        elif price >= 1:
            return f"${price:.4f}"
        elif price >= 0.01:
            return f"${price:.6f}"
        else:
            return f"${price:.8f}"
    elif currency == 'BTC':
        return f"₿{price:.8f}"
    elif currency == 'ETH':
        return f"Ξ{price:.6f}"
    elif currency == 'EUR':
        return f"€{price:.4f}"
    else:
        return f"{price:.6f}"

def format_pair_price(price: float, pair: str) -> str:
    """
    Format trading pair prices with appropriate precision
    """
    if 'BTC' in pair and 'ETH' in pair:
        return f"{price:.6f}"
    elif 'EUR/USD' == pair:
        return f"{price:.4f}"
    else:
        return f"{price:.6f}"

def format_percentage(percentage: float) -> str:
    """
    Format percentage change with appropriate sign and color indication
    """
    sign = "+" if percentage > 0 else ""
    return f"{sign}{percentage:.2f}%"

def format_market_cap(market_cap: float) -> str:
    """
    Format market cap in readable format (B for billions, M for millions)
    """
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.2f}M"
    else:
        return f"${market_cap:,.0f}"

def format_volume(volume: float) -> str:
    """
    Format trading volume in readable format
    """
    if volume >= 1_000_000_000:
        return f"${volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"${volume / 1_000_000:.2f}M"
    else:
        return f"${volume:,.0f}"

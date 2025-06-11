"""
Database module for crypto widget
Handles database connections and operations
"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json

Base = declarative_base()

class CoinPrice(Base):
    """Table for storing cryptocurrency prices"""
    __tablename__ = 'coin_prices'
    
    id = Column(Integer, primary_key=True)
    coin_id = Column(String(50), nullable=False)
    coin_name = Column(String(100), nullable=False)
    coin_symbol = Column(String(10), nullable=False)
    price_usd = Column(Float, nullable=False)
    price_btc = Column(Float)
    price_eth = Column(Float)
    price_eur = Column(Float)
    market_cap = Column(Float)
    volume_24h = Column(Float)
    change_24h = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class TradingPair(Base):
    """Table for storing trading pair data"""
    __tablename__ = 'trading_pairs'
    
    id = Column(Integer, primary_key=True)
    pair_name = Column(String(20), nullable=False)
    base_currency = Column(String(50), nullable=False)
    quote_currency = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    change_24h = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class HistoricalData(Base):
    """Table for storing historical price data"""
    __tablename__ = 'historical_data'
    
    id = Column(Integer, primary_key=True)
    coin_id = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    data_type = Column(String(20), default='price')  # 'price', 'volume', etc.

class PairHistoricalData(Base):
    """Table for storing historical trading pair data"""
    __tablename__ = 'pair_historical_data'
    
    id = Column(Integer, primary_key=True)
    pair_name = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)

class UserPreferences(Base):
    """Table for storing user preferences"""
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False)
    selected_coins = Column(Text)  # JSON string of selected coin IDs
    auto_refresh = Column(Boolean, default=True)
    refresh_interval = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatabaseManager:
    """Database manager class"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Create a new database session"""
        return self.SessionLocal()
    
    def store_coin_prices(self, coin_data: Dict):
        """Store current coin prices in the database"""
        session = self.get_session()
        try:
            for coin_id, data in coin_data.items():
                coin_price = CoinPrice(
                    coin_id=coin_id,
                    coin_name=data.get('name', ''),
                    coin_symbol=data.get('symbol', ''),
                    price_usd=data.get('usd', 0),
                    price_btc=data.get('btc', 0),
                    price_eth=data.get('eth', 0),
                    price_eur=data.get('eur', 0),
                    market_cap=data.get('usd_market_cap', 0),
                    volume_24h=data.get('usd_24h_vol', 0),
                    change_24h=data.get('usd_24h_change', 0)
                )
                session.add(coin_price)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def store_trading_pairs(self, pair_data: Dict):
        """Store trading pair data in the database"""
        session = self.get_session()
        try:
            for pair_name, data in pair_data.items():
                trading_pair = TradingPair(
                    pair_name=pair_name,
                    base_currency=data.get('base', ''),
                    quote_currency=data.get('quote', ''),
                    price=data.get('price', 0),
                    change_24h=data.get('change_24h', 0)
                )
                session.add(trading_pair)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def store_historical_data(self, coin_id: str, timestamps: List[datetime], prices: List[float]):
        """Store historical data for a coin"""
        session = self.get_session()
        try:
            # Clear old data for this coin (keep last 30 days)
            cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - 30)
            session.query(HistoricalData).filter(
                HistoricalData.coin_id == coin_id,
                HistoricalData.timestamp < cutoff_date
            ).delete()
            
            for timestamp, price in zip(timestamps, prices):
                historical_data = HistoricalData(
                    coin_id=coin_id,
                    price=price,
                    timestamp=timestamp
                )
                session.add(historical_data)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def store_pair_historical_data(self, pair_name: str, timestamps: List[datetime], prices: List[float]):
        """Store historical data for a trading pair"""
        session = self.get_session()
        try:
            # Clear old data for this pair (keep last 30 days)
            cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - 30)
            session.query(PairHistoricalData).filter(
                PairHistoricalData.pair_name == pair_name,
                PairHistoricalData.timestamp < cutoff_date
            ).delete()
            
            for timestamp, price in zip(timestamps, prices):
                pair_historical_data = PairHistoricalData(
                    pair_name=pair_name,
                    price=price,
                    timestamp=timestamp
                )
                session.add(pair_historical_data)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_latest_coin_prices(self, coin_ids: List[str]) -> Dict:
        """Get latest coin prices from database"""
        session = self.get_session()
        try:
            latest_prices = {}
            for coin_id in coin_ids:
                latest = session.query(CoinPrice).filter(
                    CoinPrice.coin_id == coin_id
                ).order_by(CoinPrice.timestamp.desc()).first()
                
                if latest:
                    latest_prices[coin_id] = {
                        'usd': latest.price_usd,
                        'btc': latest.price_btc,
                        'eth': latest.price_eth,
                        'eur': latest.price_eur,
                        'usd_market_cap': latest.market_cap,
                        'usd_24h_vol': latest.volume_24h,
                        'usd_24h_change': latest.change_24h,
                        'last_updated_at': latest.timestamp.timestamp()
                    }
            return latest_prices
        finally:
            session.close()
    
    def get_latest_trading_pairs(self) -> Dict:
        """Get latest trading pair data from database"""
        session = self.get_session()
        try:
            pairs = {}
            latest_pairs = session.query(TradingPair).all()
            
            for pair in latest_pairs:
                pairs[pair.pair_name] = {
                    'price': pair.price,
                    'change_24h': pair.change_24h,
                    'base': pair.base_currency,
                    'quote': pair.quote_currency
                }
            return pairs
        finally:
            session.close()
    
    def get_historical_data(self, coin_id: str, days: int = 7) -> Tuple[List[datetime], List[float]]:
        """Get historical data for a coin from database"""
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            historical_data = session.query(HistoricalData).filter(
                HistoricalData.coin_id == coin_id,
                HistoricalData.timestamp >= cutoff_date
            ).order_by(HistoricalData.timestamp.asc()).all()
            
            timestamps = []
            prices = []
            
            for data in historical_data:
                timestamps.append(data.timestamp)
                prices.append(data.price)
            
            return timestamps, prices
        finally:
            session.close()
    
    def get_pair_historical_data(self, pair_name: str, days: int = 7) -> Tuple[List[datetime], List[float]]:
        """Get historical data for a trading pair from database"""
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            historical_data = session.query(PairHistoricalData).filter(
                PairHistoricalData.pair_name == pair_name,
                PairHistoricalData.timestamp >= cutoff_date
            ).order_by(PairHistoricalData.timestamp.asc()).all()
            
            timestamps = []
            prices = []
            
            for data in historical_data:
                timestamps.append(data.timestamp)
                prices.append(data.price)
            
            return timestamps, prices
        finally:
            session.close()
    
    def save_user_preferences(self, session_id: str, selected_coins: List[str], 
                            auto_refresh: bool, refresh_interval: int):
        """Save user preferences to database"""
        session = self.get_session()
        try:
            # Check if preferences exist for this session
            existing = session.query(UserPreferences).filter(
                UserPreferences.session_id == session_id
            ).first()
            
            if existing:
                existing.selected_coins = json.dumps(selected_coins)
                existing.auto_refresh = auto_refresh
                existing.refresh_interval = refresh_interval
                existing.updated_at = datetime.utcnow()
            else:
                preferences = UserPreferences(
                    session_id=session_id,
                    selected_coins=json.dumps(selected_coins),
                    auto_refresh=auto_refresh,
                    refresh_interval=refresh_interval
                )
                session.add(preferences)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def load_user_preferences(self, session_id: str) -> Optional[Dict]:
        """Load user preferences from database"""
        session = self.get_session()
        try:
            preferences = session.query(UserPreferences).filter(
                UserPreferences.session_id == session_id
            ).first()
            
            if preferences:
                return {
                    'selected_coins': json.loads(preferences.selected_coins),
                    'auto_refresh': bool(preferences.auto_refresh),
                    'refresh_interval': int(preferences.refresh_interval)
                }
            return None
        finally:
            session.close()
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data from the database"""
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - days)
            
            # Clean up old coin prices
            session.query(CoinPrice).filter(
                CoinPrice.timestamp < cutoff_date
            ).delete()
            
            # Clean up old trading pairs
            session.query(TradingPair).filter(
                TradingPair.timestamp < cutoff_date
            ).delete()
            
            # Clean up old historical data
            session.query(HistoricalData).filter(
                HistoricalData.timestamp < cutoff_date
            ).delete()
            
            # Clean up old pair historical data
            session.query(PairHistoricalData).filter(
                PairHistoricalData.timestamp < cutoff_date
            ).delete()
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
import requests
import feedparser
import json
import time
from datetime import datetime
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import Config
from telegram_bot import TelegramBot
from sentiment_analyzer import FinSentimentAnalyzer

# Добавьте в начало main.py, после импорта Config
print("Версия 0.1a")
print("=== DEBUG: Проверка переменных окружения ===")
print(f"TELEGRAM_WORKER_URL: {os.getenv('TELEGRAM_WORKER_URL', 'NOT SET')}")
print(f"TELEGRAM_BOT_TOKEN: {os.getenv('TELEGRAM_BOT_TOKEN', 'NOT SET')[:10] if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET'}...")
print(f"TELEGRAM_CHAT_ID: {os.getenv('TELEGRAM_CHAT_ID', 'NOT SET')}")
print("="*29)

def get_bitcoin_price():
    """
    Получает текущую цену Bitcoin с Binance
    Возвращает цену в USD и 24h изменение в процентах
    """
    try:
        # Binance API endpoint для получения цены BTC/USDT [citation:10]
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        price = float(data['lastPrice'])
        price_change_percent = float(data['priceChangePercent'])
        
        return {
            'price': price,
            'price_change_percent': price_change_percent,
            'high_24h': float(data['highPrice']),
            'low_24h': float(data['lowPrice']),
            'volume': float(data['volume'])
        }
    except Exception as e:
        print(f"⚠️ Ошибка получения цены BTC: {e}")
        return None
    
class NewsMonitor:
    def __init__(self):
        # Инициализируем анализатор FinBERT
        print("Инициализация анализатора тональности FinBERT...")
        self.sentiment_analyzer = FinSentimentAnalyzer()
        
    def fetch_crypto_news(self):
        """Получение новостей из RSS-лент"""
        
        # Список источников
        rss_feeds = [
            'https://cointelegraph.com/rss',
            'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'https://bitcoinmagazine.com/feed',
            'https://cryptoslate.com/feed/',
            'https://decrypt.co/feed'
        ]
        
        all_articles = []
        
        for feed_url in rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Последние 10 статей из каждого источника
                    article = {
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', ''),
                        'source': feed_url.split('/')[2]
                    }
                    all_articles.append(article)
                    
            except Exception as e:
                print(f"Ошибка при парсинге {feed_url}: {e}")
                continue
        
        return all_articles
    
    def analyze_news_sentiment(self, news_articles):
        """Анализ тональности всех новостей с помощью FinBERT"""
        results = []
        
        for article in news_articles:
            # Объединяем заголовок и краткое содержание
            text = article['title']
            if article.get('summary'):
                text += ". " + article['summary']
            
            # Анализируем тональность
            sentiment_result = self.sentiment_analyzer.analyze_sentiment(text)
            
            # Получаем сигнал
            signal, action = self.sentiment_analyzer.get_signal(sentiment_result['sentiment_score'])
            
            results.append({
                'title': article['title'][:100] + "...",
                'source': article['source'],
                'sentiment_score': sentiment_result['sentiment_score'],
                'positive': sentiment_result['positive_prob'],
                'neutral': sentiment_result['neutral_prob'],
                'negative': sentiment_result['negative_prob'],
                'signal': signal,
                'action': action,
                'link': article['link']
            })
        
        return results


if __name__ == "__main__":
    print("🚀 ЗАПУСК КРИПТО-МОНИТОРА НАСТРОЕНИЙ (FinBERT)")
    print("="*60)
    
    # Проверяем конфигурацию
    if not Config.validate():
        print("❌ Ошибка: Необходимо настроить .env файл")
        print("   Скопируйте .env.example в .env и заполните данными")
        sys.exit(1)
    
    # Инициализируем Telegram бота из конфига
    print("\n📱 Инициализация Telegram бота...")
    telegram_bot = TelegramBot(
        worker_url=Config.TELEGRAM_WORKER_URL,
        bot_token=Config.TELEGRAM_BOT_TOKEN,
        chat_id=Config.TELEGRAM_CHAT_ID
    )   
    # Отправляем приветственное сообщение
    # telegram_bot.send_message("🚀 Запущен мониторинг крипто-новостей. Анализирую рынок...")
    
    # Получаем цену BTC
    print("\n💰 Получение текущей цены Bitcoin...")
    btc_data = get_bitcoin_price()
    
    # Создаем монитор
    print("\n🔧 Инициализация анализатора новостей...")
    monitor = NewsMonitor()
    
    # Получаем новости
    print("\n📰 Получение свежих новостей...")
    news = monitor.fetch_crypto_news()
    
    if news:
        print(f"✅ Получено {len(news)} новостей")
        
        # Анализируем настроения
        print("\n🔍 Анализ тональности с помощью FinBERT...")
        analysis_results = monitor.analyze_news_sentiment(news)
        
        # Сортируем новости по тональности
        sorted_by_sentiment = sorted(analysis_results, key=lambda x: x['sentiment_score'], reverse=True)
        
        # Статистика
        avg_sentiment = sum(r['sentiment_score'] for r in analysis_results) / len(analysis_results)
        positive_count = sum(1 for r in analysis_results if r['sentiment_score'] > 0.05)
        negative_count = sum(1 for r in analysis_results if r['sentiment_score'] < -0.05)
        neutral_count = len(analysis_results) - positive_count - negative_count
        
        # Формируем статистику для отчёта
        sentiment_stats = {
            'avg_sentiment': avg_sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'positive_percent': positive_count / len(analysis_results) * 100,
            'negative_percent': negative_count / len(analysis_results) * 100,
            'neutral_percent': neutral_count / len(analysis_results) * 100
        }
        
        # Определяем итоговый сигнал
        combined_signal = {}
        combined_signal['avg_sentiment'] = avg_sentiment
        if avg_sentiment > 0.1:
            combined_signal['message'] = "🐂 БЫЧИЙ СИГНАЛ - Рынок настроен позитивно"
            combined_signal['advice'] = "Рассмотрите возможность увеличения позиций"
            combined_signal['type'] = "bullish"
        elif avg_sentiment < -0.1:
            combined_signal['message'] = "🐻 МЕДВЕЖИЙ СИГНАЛ - Преобладает негатив"
            combined_signal['advice'] = "Будьте осторожны с новыми покупками"
            combined_signal['type'] = "bearish"
        else:
            combined_signal['message'] = "⚪ НЕЙТРАЛЬНЫЙ СИГНАЛ - Рынок не определился"
            combined_signal['advice'] = "Продолжайте наблюдение"
            combined_signal['type'] = "neutral"
        
        # Отправляем полный отчёт в Telegram
        print("\n📤 Отправка отчёта в Telegram...")
        success = telegram_bot.send_analysis_report(
            btc_data=btc_data,
            sentiment_stats=sentiment_stats,
            top_positive=sorted_by_sentiment[:5],
            top_negative=sorted_by_sentiment[-5:][::-1],
            combined_signal=combined_signal
        )
        
        if success:
            print("✅ Отчёт успешно отправлен в Telegram")
        else:
            print("⚠️ Не удалось отправить отчёт в Telegram")
        
        # Также выводим краткую информацию в консоль
        print("\n" + "="*60)
        print("📊 КРАТКАЯ АНАЛИТИКА")
        print("="*60)
        if btc_data:
            print(f"💰 BTC: ${btc_data['price']:,.2f} ({btc_data['price_change_percent']:+.2f}%)")
        print(f"📊 Средняя тональность: {avg_sentiment:.3f}")
        print(f"🎯 Сигнал: {combined_signal['message']}")
        print("="*60)
        
    else:
        error_msg = "❌ Не удалось получить новости. Проверьте подключение к интернету."
        print(error_msg)
        telegram_bot.send_message(error_msg)
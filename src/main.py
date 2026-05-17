"""
Крипто-монитор настроений без feedparser
"""
import requests
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import os
from config import Config
from sentiment_analyzer import FinSentimentAnalyzer
from telegram_bot import TelegramBot

def get_bitcoin_price():
    """Получает текущую цену Bitcoin с Binance"""
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        return {
            'price': float(data['lastPrice']),
            'price_change_percent': float(data['priceChangePercent']),
            'high_24h': float(data['highPrice']),
            'low_24h': float(data['lowPrice']),
            'volume': float(data['volume'])
        }
    except Exception as e:
        print(f"⚠️ Ошибка получения цены BTC: {e}")
        return None

class NewsMonitor:
    def __init__(self):
        print("Инициализация анализатора тональности...")
        self.sentiment_analyzer = FinSentimentAnalyzer()
    
    def fetch_crypto_news(self):
        """Получение новостей через RSS (без feedparser)"""
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
                print(f"  Парсинг {feed_url}...")
                response = requests.get(feed_url, timeout=30)
                response.raise_for_status()
                
                root = ET.fromstring(response.content)
                
                # Поиск всех элементов item
                for item in root.findall('.//item')[:10]:
                    title = item.find('title')
                    title_text = title.text.strip() if title is not None and title.text else ''
                    
                    description = item.find('description')
                    desc_text = description.text.strip() if description is not None and description.text else ''
                    
                    link = item.find('link')
                    link_text = link.text if link is not None else ''
                    
                    pub_date = item.find('pubDate')
                    date_text = pub_date.text if pub_date is not None else ''
                    
                    if title_text:
                        article = {
                            'title': title_text,
                            'summary': desc_text,
                            'link': link_text,
                            'published': date_text,
                            'source': feed_url.split('/')[2]
                        }
                        all_articles.append(article)
                        
            except ET.ParseError as e:
                print(f"  Ошибка парсинга XML {feed_url}: {e}")
            except Exception as e:
                print(f"  Ошибка при парсинге {feed_url}: {e}")
            
            time.sleep(1)  # Небольшая задержка между запросами
        
        return all_articles
    
    def analyze_news_sentiment(self, news_articles):
        """Анализ тональности всех новостей"""
        results = []
        
        for article in news_articles:
            text = article['title']
            if article.get('summary'):
                text += ". " + article['summary']
            
            sentiment_result = self.sentiment_analyzer.analyze_sentiment(text)
            signal, action = self.sentiment_analyzer.get_signal(sentiment_result['sentiment_score'])
            
            results.append({
                'title': article['title'][:100] + "..." if len(article['title']) > 100 else article['title'],
                'source': article['source'],
                'sentiment_score': sentiment_result['sentiment_score'],
                'signal': signal,
                'action': action,
                'link': article['link']
            })
        
        return results

if __name__ == "__main__":
    print("🚀 ЗАПУСК КРИПТО-МОНИТОРА НАСТРОЕНИЙ")
    print("="*60)
    
    # Проверяем конфигурацию
    if not Config.validate():
        print("❌ Ошибка: Необходимо настроить секреты")
        exit(1)
    
    # Инициализируем Telegram бота
    print("\n📱 Инициализация Telegram бота...")
    telegram_bot = TelegramBot(
        worker_url=Config.TELEGRAM_WORKER_URL,
        bot_token=Config.TELEGRAM_BOT_TOKEN,
        chat_id=Config.TELEGRAM_CHAT_ID
    )
    
    # Получаем цену BTC
    print("\n💰 Получение цены Bitcoin...")
    btc_data = get_bitcoin_price()
    if btc_data:
        print(f"   BTC: ${btc_data['price']:,.2f} ({btc_data['price_change_percent']:+.2f}%)")
    
    # Создаем монитор
    monitor = NewsMonitor()
    
    # Получаем новости
    print("\n📰 Получение новостей...")
    news = monitor.fetch_crypto_news()
    
    if news:
        print(f"✅ Получено {len(news)} новостей")
        
        # Анализируем
        print("\n🔍 Анализ тональности...")
        results = monitor.analyze_news_sentiment(news)
        
        # Сортируем
        sorted_results = sorted(results, key=lambda x: x['sentiment_score'], reverse=True)
        
        # Статистика
        avg_sentiment = sum(r['sentiment_score'] for r in results) / len(results)
        positive = sum(1 for r in results if r['sentiment_score'] > 0.05)
        negative = sum(1 for r in results if r['sentiment_score'] < -0.05)
        neutral = len(results) - positive - negative
        
        sentiment_stats = {
            'avg_sentiment': avg_sentiment,
            'positive_count': positive,
            'negative_count': negative,
            'neutral_count': neutral,
            'positive_percent': positive / len(results) * 100,
            'negative_percent': negative / len(results) * 100,
            'neutral_percent': neutral / len(results) * 100
        }
        
        # Определяем сигнал
        if avg_sentiment > 0.1:
            signal_msg = "🐂 БЫЧИЙ СИГНАЛ - Рынок настроен позитивно"
            advice = "Рассмотрите возможность увеличения позиций"
        elif avg_sentiment < -0.1:
            signal_msg = "🐻 МЕДВЕЖИЙ СИГНАЛ - Преобладает негатив"
            advice = "Будьте осторожны с новыми покупками"
        else:
            signal_msg = "⚪ НЕЙТРАЛЬНЫЙ СИГНАЛ - Рынок не определился"
            advice = "Продолжайте наблюдение"
        
        combined_signal = {
            'message': signal_msg,
            'advice': advice,
            'avg_sentiment': avg_sentiment
        }
        
        # Отправляем в Telegram
        print("\n📤 Отправка отчёта в Telegram...")
        success = telegram_bot.send_analysis_report(
            btc_data=btc_data,
            sentiment_stats=sentiment_stats,
            top_positive=sorted_results[:5],
            top_negative=sorted_results[-5:][::-1],
            combined_signal=combined_signal
        )
        
        if success:
            print("✅ Отчёт отправлен!")
        else:
            print("❌ Не удалось отправить отчёт")
            
    else:
        print("❌ Не удалось получить новости")
        telegram_bot.send_message("⚠️ Мониторинг завершился ошибкой: не удалось получить новости")
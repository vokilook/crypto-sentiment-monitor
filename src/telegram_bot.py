"""
Модуль для отправки сообщений в Telegram с повторными попытками
"""
import requests
from datetime import datetime
import time

class TelegramBot:
    def __init__(self, worker_url: str, bot_token: str, chat_id: str, max_retries: int = 5):
        """
        Инициализация Telegram бота
        
        Args:
            worker_url: URL вашего Cloudflare Worker (прокси)
            bot_token: Токен бота
            chat_id: ID чата для отправки сообщений
            max_retries: Максимальное количество попыток отправки
        """
        self.worker_url = worker_url.rstrip('/')
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_retries = max_retries  # <-- ЭТА СТРОКА БЫЛА ПРОПУЩЕНА
    
    def send_message(self, message: str, parse_mode: str = "HTML", retry_count: int = 0) -> bool:
        """
        Отправляет текстовое сообщение в Telegram с повторными попытками при ошибке
        
        Args:
            message: Текст сообщения
            parse_mode: Форматирование (HTML или Markdown)
            retry_count: Текущий номер попытки (для внутреннего использования)
        
        Returns:
            bool: Успешность отправки
        """
        try:
            url = f"{self.worker_url}/bot{self.bot_token}/sendMessage"
            params = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            print(f"📤 Отправка сообщения в Telegram (попытка {retry_count + 1}/{self.max_retries})...")
            response = requests.post(url, json=params, timeout=30)
            
            if response.status_code == 200:
                print("✅ Сообщение успешно отправлено в Telegram")
                return True
            else:
                print(f"❌ Ошибка отправки: HTTP {response.status_code}")
                print(f"   Ответ сервера: {response.text[:200]}")
                
                if retry_count < self.max_retries - 1:
                    wait_time = 60
                    print(f"⏳ Повторная попытка через {wait_time} секунд...")
                    time.sleep(wait_time)
                    return self.send_message(message, parse_mode, retry_count + 1)
                else:
                    print(f"❌ Сообщение не отправлено после {self.max_retries} попыток")
                    return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Таймаут при отправке (попытка {retry_count + 1})")
            if retry_count < self.max_retries - 1:
                wait_time = 60
                print(f"⏳ Повторная попытка через {wait_time} секунд...")
                time.sleep(wait_time)
                return self.send_message(message, parse_mode, retry_count + 1)
            return False
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Ошибка соединения (попытка {retry_count + 1})")
            if retry_count < self.max_retries - 1:
                wait_time = 60
                print(f"⏳ Повторная попытка через {wait_time} секунд...")
                time.sleep(wait_time)
                return self.send_message(message, parse_mode, retry_count + 1)
            return False
            
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            if retry_count < self.max_retries - 1:
                wait_time = 60
                print(f"⏳ Повторная попытка через {wait_time} секунд...")
                time.sleep(wait_time)
                return self.send_message(message, parse_mode, retry_count + 1)
            return False
    
    def send_analysis_report(self, btc_data: dict, sentiment_stats: dict, 
                            top_positive: list, top_negative: list, 
                            combined_signal: dict):
        """
        Отправляет форматированный аналитический отчёт
        """
        message = self._format_report(btc_data, sentiment_stats, top_positive, 
                                      top_negative, combined_signal)
        return self.send_message(message, parse_mode="HTML")
    
    def _format_report(self, btc_data: dict, sentiment_stats: dict,
                      top_positive: list, top_negative: list, combined_signal: dict) -> str:
        """
        Форматирует отчёт в HTML для Telegram
        """
        now = datetime.now()
        message = f"<b>📊 CRYPTO SENTIMENT REPORT</b>\n"
        message += f"<i>{now.strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
        message += f"{'='*29}\n\n"
        
        # Секция цены BTC
        if btc_data:
            message += f"💰 <b>BITCOIN PRICE</b>\n"
            message += f"└── ${btc_data['price']:,.2f}\n"
            
            change = btc_data['price_change_percent']
            if change >= 0:
                message += f"└── 📈 24h: <b>+{change:.2f}%</b>\n"
            else:
                message += f"└── 📉 24h: <b>{change:.2f}%</b>\n"
            
            message += f"└── 📊 24h High: ${btc_data.get('high_24h', 0):,.2f}\n"
            message += f"└── 📊 24h Low: ${btc_data.get('low_24h', 0):,.2f}\n\n"
        
        # Секция настроений
        message += f"📈 <b>SENTIMENT ANALYSIS</b>\n"
        message += f"└── 🎯 Average: <b>{sentiment_stats['avg_sentiment']:.3f}</b>\n"
        message += f"└── 🟢 Positive: {sentiment_stats['positive_count']} ({sentiment_stats['positive_percent']:.1f}%)\n"
        message += f"└── ⚪ Neutral: {sentiment_stats['neutral_count']} ({sentiment_stats['neutral_percent']:.1f}%)\n"
        message += f"└── 🔴 Negative: {sentiment_stats['negative_count']} ({sentiment_stats['negative_percent']:.1f}%)\n\n"
        
        # Топ позитивных новостей
        if top_positive:
            message += f"🟢 <b>TOP 5 POSITIVE NEWS</b>\n"
            for i, news in enumerate(top_positive[:5], 1):
                title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
                message += f"{i}. {title}\n"
                message += f"   └── 📍 {news['source']} | +{news['sentiment_score']:.3f}\n"
            message += "\n"
        
        # Топ негативных новостей
        if top_negative:
            message += f"🔴 <b>TOP 5 NEGATIVE NEWS</b>\n"
            for i, news in enumerate(top_negative[:5], 1):
                title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
                message += f"{i}. {title}\n"
                message += f"   └── 📍 {news['source']} | {news['sentiment_score']:.3f}\n"
            message += "\n"
        
        # Итоговый сигнал
        message += f"{'='*29}\n"
        message += f"🎯 <b>FINAL SIGNAL</b> <b>{sentiment_stats['avg_sentiment']:.3f}</b>\n"
        message += f"{'='*29}\n"
        message += f"{combined_signal['message']}\n"
        
        if combined_signal.get('advice'):
            message += f"\n💡 <b>Advice:</b> {combined_signal['advice']}"
        
        return message
    
    def send_quick_update(self, btc_price: float, sentiment_score: float, signal: str):
        """
        Отправляет краткое обновление (для быстрых уведомлений)
        """
        message = f"<b>🔄 Quick Update</b>\n"
        message += f"💰 BTC: ${btc_price:,.2f}\n"
        message += f"📊 Sentiment: {sentiment_score:.3f}\n"
        message += f"🎯 Signal: {signal}"
        
        return self.send_message(message)


# Пример использования
if __name__ == "__main__":
    WORKER_URL = "https://old-scene-b197.vokilook.workers.dev"
    BOT_TOKEN = "6536518582:AAFWk_uRw3x0imnxhyT8kgNhb_3xOFO-yd0"
    CHAT_ID = "-1001906145218"
    
    bot = TelegramBot(WORKER_URL, BOT_TOKEN, CHAT_ID, max_retries=5)
    
    # Тестовое сообщение
    bot.send_message("🚀 Бот запущен и готов к работе!")
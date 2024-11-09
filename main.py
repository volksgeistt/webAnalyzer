import requests
import time
import ssl
import socket
from urllib.parse import urlparse
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

class WebsitePerformanceAnalyzer:
    def __init__(self):
        self.logger = self._setup_logging()
        self.selenium_available = False
        try:
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.support.ui import WebDriverWait
            from webdriver_manager.chrome import ChromeDriverManager
            
            self.chrome_options = self._setup_chrome_options()
            self.service = Service(ChromeDriverManager().install())
            self.selenium_available = True
        except Exception as e:
            self.logger.warning(f"Selenium setup failed: {str(e)}. Will run without browser-based metrics.")
        
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('website_performance.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)

    def _setup_chrome_options(self):
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return options

    def measure_ttfb(self, url):
        try:
            start_time = time.time()
            response = requests.get(url)
            ttfb = response.elapsed.total_seconds()
            return ttfb
        except Exception as e:
            self.logger.error(f"Error measuring TTFB: {str(e)}")
            return None

    def measure_response_time(self, url):
        try:
            start_time = time.time()
            response = requests.get(url)
            return time.time() - start_time
        except Exception as e:
            self.logger.error(f"Error measuring response time: {str(e)}")
            return None

    def check_ssl_security(self, url):
        try:
            hostname = urlparse(url).hostname
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443)) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    return {
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'expiry': cert['notAfter'],
                        'subject': dict(x[0] for x in cert['subject'])
                    }
        except Exception as e:
            self.logger.error(f"Error checking SSL: {str(e)}")
            return None

    def check_headers(self, url):
        try:
            response = requests.head(url)
            return {
                'server': response.headers.get('server'),
                'content_type': response.headers.get('content-type'),
                'content_length': response.headers.get('content-length'),
                'cache_control': response.headers.get('cache-control'),
                'security_headers': {
                    'strict_transport_security': response.headers.get('strict-transport-security'),
                    'x_content_type_options': response.headers.get('x-content-type-options'),
                    'x_frame_options': response.headers.get('x-frame-options'),
                    'content_security_policy': response.headers.get('content-security-policy')
                }
            }
        except Exception as e:
            self.logger.error(f"Error checking headers: {str(e)}")
            return None

    def measure_web_vitals(self, url):
        if not self.selenium_available:
            self.logger.info("Selenium not available, skipping web vitals measurement")
            return None
            
        try:
            from selenium import webdriver
            driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
            
            start_time = time.time()
            driver.get(url)
            
            performance_metrics = driver.execute_script("""
                const performance = window.performance;
                const navigation = performance.getEntriesByType('navigation')[0];
                const paint = performance.getEntriesByType('paint');
                
                return {
                    'loadTime': navigation.loadEventEnd - navigation.startTime,
                    'domContentLoaded': navigation.domContentLoadedEventEnd - navigation.startTime,
                    'firstPaint': paint.find(p => p.name === 'first-paint')?.startTime,
                    'firstContentfulPaint': paint.find(p => p.name === 'first-contentful-paint')?.startTime
                }
            """)
            
            driver.quit()
            return performance_metrics
            
        except Exception as e:
            self.logger.error(f"Error measuring web vitals: {str(e)}")
            return None

    def analyze_network_performance(self, url):
        if not self.selenium_available:
            return self._analyze_network_basic(url)
            
        try:
            from selenium import webdriver
            driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
            
            driver.get(url)
            performance_logs = driver.execute_script("""
                return window.performance.getEntries().map(entry => {
                    return {
                        name: entry.name,
                        entryType: entry.entryType,
                        duration: entry.duration,
                        initiatorType: entry.initiatorType
                    }
                });
            """)
            
            driver.quit()
            
            analysis = {
                'total_requests': len(performance_logs),
                'slow_resources': [
                    entry for entry in performance_logs 
                    if entry['duration'] > 1000
                ],
                'resource_types': {}
            }
            
            for entry in performance_logs:
                resource_type = entry.get('initiatorType', 'other')
                analysis['resource_types'][resource_type] = analysis['resource_types'].get(resource_type, 0) + 1
                
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing network performance: {str(e)}")
            return self._analyze_network_basic(url)

    def _analyze_network_basic(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            scripts = len(soup.find_all('script'))
            styles = len(soup.find_all('link', rel='stylesheet'))
            images = len(soup.find_all('img'))
            
            return {
                'total_requests': scripts + styles + images + 1,  
                'resource_types': {
                    'scripts': scripts,
                    'stylesheets': styles,
                    'images': images
                },
                'page_size': len(response.content),
                'content_type': response.headers.get('content-type')
            }
        except Exception as e:
            self.logger.error(f"Error in basic network analysis: {str(e)}")
            return None

    def generate_optimization_recommendations(self, url, performance_data):
        recommendations = []
        
        if performance_data.get('ttfb', 0) and performance_data['ttfb'] > 0.5:
            recommendations.append({
                'issue': 'High Time to First Byte',
                'recommendation': 'Optimize server response time, consider caching or CDN usage'
            })
        
        if not performance_data.get('ssl_info'):
            recommendations.append({
                'issue': 'SSL Certificate Issues',
                'recommendation': 'Ensure proper SSL certificate installation and configuration'
            })
        
        headers = performance_data.get('headers', {})
        if headers:
            if not headers.get('cache_control'):
                recommendations.append({
                    'issue': 'Missing Cache Control',
                    'recommendation': 'Implement proper cache control headers'
                })
            
            security_headers = headers.get('security_headers', {})
            if not security_headers.get('strict_transport_security'):
                recommendations.append({
                    'issue': 'Missing HSTS Header',
                    'recommendation': 'Implement HTTP Strict Transport Security'
                })
        
        web_vitals = performance_data.get('web_vitals', {})
        if web_vitals:
            if web_vitals.get('firstContentfulPaint', 0) > 2000:
                recommendations.append({
                    'issue': 'Slow First Contentful Paint',
                    'recommendation': 'Optimize critical rendering path, implement lazy loading'
                })
        
        return recommendations

    def run_complete_analysis(self, url):
        self.logger.info(f"Starting complete analysis for {url}")
        
        results = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'ttfb': self.measure_ttfb(url),
            'response_time': self.measure_response_time(url),
            'ssl_info': self.check_ssl_security(url),
            'headers': self.check_headers(url),
            'web_vitals': self.measure_web_vitals(url),
            'network': self.analyze_network_performance(url)
        }
        
        results['recommendations'] = self.generate_optimization_recommendations(url, results)
        
        with open(f'analysis_results_{int(time.time())}.json', 'w') as f:
            json.dump(results, f, indent=4)
            
        return results

def main():
    analyzer = WebsitePerformanceAnalyzer()
    
    url = input("Enter website URL to analyze: ")
    results = analyzer.run_complete_analysis(url)
    
    print("\nAnalysis Results:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()

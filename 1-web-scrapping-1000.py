# -*- coding: utf-8 -*-
import scrapy
import os
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.crawler import CrawlerProcess
from urllib import parse
from os import path
from scrapy.http.response.html import HtmlResponse
import multiprocessing
from typing import List

class NewsSpider(CrawlSpider):

    DOWNLOAD_HANDLERS = {
    'https': 'my.custom.downloader.handler.https.HttpsDownloaderIgnoreCNError',
    }

    name = 'crawler_pagina12'
    # solo descargar paginas desde estos dominios
    allowed_domains = ('www.pagina12.com.ar','pagina12.com.ar')
    # paginas a descargar
    max_pages = 10 # valor por defecto 10 noticias por seccion
    page_count = 0 # contador de paginas descargadas por defecto en 0

    rules = (
        # Rule for article pages (e.g., /999999-texto)
        Rule(LinkExtractor(
            allow=r'.+/\d{6,}-[^/]+',
            deny=r'.+(/catamarca12|/dialogo).+',
            deny_domains=['auth.pagina12.com.ar'],
            canonicalize=True,
            deny_extensions=['7z', '7zip', 'apk', 'bz2', 'cdr', 'dmg', 'ico', 'iso', 'tar', 'tar.gz', 'pdf', 'docx', 'jpg', 'png', 'css', 'js']
        ), callback='parse_response', follow=False),
    )
    
    # configuracion de scrappy, ver https://docs.scrapy.org/en/latest/topics/settings.html
    # la var de clase debe llamarse "custom settings"
    custom_settings = {
        # mentir el user agent
        'USER_AGENT': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'LOG_ENABLED': True,
        'LOG_LEVEL': 'INFO',
        # no descargar paginas mas alla de 1 link desde la pagina de origen
        'DEPTH_LIMIT': 2,
        # ignorar robots.txt (que feo eh)
        'ROBOTSTXT_OBEY': False,
        # esperar entre 0.5*DOWNLOAD_DELAY y 1.5*DOWNLOAD_DELAY segundo entre descargas
        'DOWNLOAD_DELAY': 2.5,
        'RANDOMIZE_DOWNLOAD_DELAY': True
    }

    def __init__(self, save_pages_in_dir='.', *args, **kwargs):
        super().__init__(*args, **kwargs)
        # guardar el directorio en donde vamos a descargar las paginas
        self.basedir = save_pages_in_dir
        self.page_count = kwargs.get('current_pages', 0)
        self.max_pages = kwargs.get('max_pages', 100)

    def parse_response(self, response:HtmlResponse):
        """
        Este metodo es llamado por cada url que descarga Scrappy.
        response.url contiene la url de la pagina,
        response.body contiene los bytes del contenido de la pagina.
        """
        if self.page_count <= self.max_pages:
            # el nombre de archivo es lo que esta luego de la ultima "/"
            html_filename = path.join(self.basedir,parse.quote(response.url[response.url.rfind("/")+1:]))
            if not html_filename.endswith(".html"):
                html_filename+=".html"
            # decodificar el HTML
            html_content = response.body.decode("utf-8")
            
            # chequear si contiene el marcador de paywall
            if '<div class="paywall-inner-text">' in html_content:
                print("Página omitida (paywall detectado):", html_filename)
            else:
                if '<div class="author-hero">' in html_content:
                    print("Página omitida (pagina de autor detectada):", html_filename)
                else:
                    self.page_count += 1
                    print("Página guardada en:", html_filename)
                    with open(html_filename, "wt", encoding="utf-8") as html_file:
                        html_file.write(html_content)
        else:
            self.crawler.engine.close_spider(self, f"Alcanzado límite de {self.max_pages} páginas ")

def start_crawler(save_pages_in_dir:str, start_urls:List[str], current_pages:int, max_pages:int, result_dict:multiprocessing.Queue):
    def spider_closed(spider, reason):
        result = {
            "pages_scraped": spider.page_count,
            "reason": reason
        }
        result_dict.put(result)   # Enviar el resultado al proceso padre
        
    process = CrawlerProcess()

    crawler = process.create_crawler(NewsSpider)

    # Conecto signals para poder tomar el conteo de páginas scrapeadas
    crawler.signals.connect(spider_closed, signal=scrapy.signals.spider_closed)

    process.crawl(
        crawler,
        save_pages_in_dir=save_pages_in_dir,
        start_urls=start_urls,
        current_pages=current_pages,
        max_pages=max_pages
    )
    
    process.start()

def create_directory(dir_path: str):
    if not path.exists(dir_path):
        try:
            os.mkdir(dir_path)
            print(f"Directory '{dir_path}' created successfully")
        except FileExistsError:
            print(f"Directory '{dir_path}' already exists")
        except OSError as e:
            print(f"Error creating directory: {e}")

if __name__ == "__main__":
    DIR_BASE="./1000paginas"
    create_directory(DIR_BASE)
    secciones = ['el-mundo','el-pais','economia','sociedad']
    # Cantidad máxima de páginas por sección a scrapear
    max_pages_por_seccion = 1000
    for seccion in secciones:
        print("//////////////////////////////////////")
        print(f" Scrapeando sección {seccion}")
        print("//////////////////////////////////////")
        DIR_SECCION=f"{DIR_BASE}/{seccion}"
        create_directory(DIR_SECCION)
        # Ejecutar al crawler en un proceso separado, sino al 
        # volver a arrancar con la prox pagina de indice de noticias,
        # el crawler de scrappy da error. Esto es un fix para un problema particular de scrappy.
        seccion_count = 0
        page_index = 1
        while seccion_count < max_pages_por_seccion:
            start_url=f'http://www.pagina12.com.ar/secciones/{seccion}?page={page_index}'
            print("|||")
            print(f"||| Iniciando scrapper para {start_url}")
            print("|||")      
            q = multiprocessing.Queue()
            process = multiprocessing.Process(
                target=start_crawler,
                args=(DIR_EN_DONDE_GUARDAR_PAGINAS,
                    [start_url],
                    seccion_count,
                    max_pages_por_seccion,
                    q
                )
            )
            process.start()
            process.join()
            process_result = q.get()
            seccion_count = process_result["pages_scraped"]
            print(f"||| Acumulado de páginas scrapeadas {seccion_count} de {max_pages_por_seccion}")
            page_index += 1

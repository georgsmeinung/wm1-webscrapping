# -*- coding: utf-8 -*-
import scrapy
import os
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urllib.parse import urlparse
from scrapy.utils.response import open_in_browser
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
    cont_pagina = 0
    max_paginas = 1000
    # solo descargar paginas desde estos dominios
    allowed_domains = ('www.pagina12.com.ar','pagina12.com.ar')
    
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
    
    def parse_response(self, response:HtmlResponse):
          """
          Este metodo es llamado por cada url que descarga Scrappy.
          response.url contiene la url de la pagina,
          response.body contiene los bytes del contenido de la pagina.
          """
          if self.cont_pagina >= self.max_paginas:
                return
          else:
              self.cont_pagina += 1
          # el nombre de archivo es lo que esta luego de la ultima "/"
          html_filename = path.join(self.basedir,parse.quote(response.url[response.url.rfind("/")+1:]))
          if not html_filename.endswith(".html"):
              html_filename+=".html"
          print("URL:",response.url, "Pagina guardada en:", html_filename)
          # sabemos que pagina 12 usa encoding utf8
          with open(html_filename, "wt") as html_file:
              html_file.write(response.body.decode("utf-8"))
          

def start_crawler(save_pages_in_dir:str, start_urls:List[str]):
    crawler = CrawlerProcess()
    crawler.crawl(NewsSpider, save_pages_in_dir = save_pages_in_dir, start_urls = start_urls)
    crawler.start()


if __name__ == "__main__":
   DIR_EN_DONDE_GUARDAR_PAGINAS=f"./paginas"
   if not path.exists(DIR_EN_DONDE_GUARDAR_PAGINAS):
       # Create the directory
       try:
           os.mkdir(DIR_EN_DONDE_GUARDAR_PAGINAS)
           print(f"Directory '{DIR_EN_DONDE_GUARDAR_PAGINAS}' created successfully")
       except FileExistsError:
           print(f"Directory '{DIR_EN_DONDE_GUARDAR_PAGINAS}' already exists")
       except OSError as e:
           print(f"Error creating directory: {e}")
           
   secciones = ['el-mundo','el-pais','economia','sociedad']
   for seccion in secciones:
       print(f"Scrapeando seccion {seccion}")
       DIR_EN_DONDE_GUARDAR_PAGINAS=f"./paginas/{seccion}"
       if not path.exists(DIR_EN_DONDE_GUARDAR_PAGINAS):
           # Create the directory
           try:
               os.mkdir(DIR_EN_DONDE_GUARDAR_PAGINAS)
               print(f"Directory '{DIR_EN_DONDE_GUARDAR_PAGINAS}' created successfully")
           except FileExistsError:
               print(f"Directory '{DIR_EN_DONDE_GUARDAR_PAGINAS}' already exists")
           except OSError as e:
               print(f"Error creating directory: {e}")
       # Ejecutar al crawler en un proceso separado, sino al 
       # volver a arrancar con la prox pagina de indice de noticias,
       # el crawler de scrappy da error. Esto es un fix para un problema particular de scrappy.
       process = multiprocessing.Process(target=start_crawler, args=(DIR_EN_DONDE_GUARDAR_PAGINAS, [f'http://www.pagina12.com.ar/secciones/{seccion}']))
       process.start()
       process.join()


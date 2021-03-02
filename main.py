from notion.client import NotionClient
from notion.block import PageBlock, ToggleBlock, TextBlock
from collections import defaultdict
from google.cloud import translate
import threading
import requests
import time
import os


def translate_text(text="YOUR_TEXT_TO_TRANSLATE", project_id="notion-duolingo"):
    # TODO redis or sqlite for caching translations
    client = translate.TranslationServiceClient()
    location = "global"
    parent = f"projects/{project_id}/locations/{location}"
    
    # noinspection PyTypeChecker
    response = client.translate_text(request={
        "parent": parent,
        "contents": [text],
        "mime_type": "text/plain",
        "source_language_code": "fr",  # change the source language as needed
        "target_language_code": "en-US",  # change the target language as needed
    }
    )
    
    if response.translations:
        return response.translations[0].translated_text
    return text


def notion_duolingo():
    key = os.getenv('NOTION_KEY')
    client = NotionClient(token_v2=key)
    page = client.get_block(os.getenv('BASE_PAGE'))
    
    table_page_url = os.getenv('TABLE_URL')
    cv = client.get_collection_view(table_page_url)
    
    data = defaultdict(list)  # TODO use a set instead
    for row in cv.collection.get_rows():
        print(row)
        data[row.category].append(row.word.replace('__', ''))
    
    def write_toggle(english, french, category_page):
        try:
            toggle = category_page.children.add_new(ToggleBlock, title=english)
            print(f'Wrting {english} --> {french}')
            try:
                toggle.children.add_new(TextBlock, title=french)
            except requests.exceptions.HTTPError:
                toggle.remove()
                return False
            return True
        except requests.exceptions.HTTPError:
            print('Notion error writing, trying again')
            return False
    
    def build_category_page(category, items):
        newpage = page.children.add_new(PageBlock, title=category)
        for french_word in items:
            english_word = translate_text(french_word)
            success = write_toggle(english_word, french_word, newpage)
            if not success:
                time.sleep(3)
                write_toggle(english_word, french_word, newpage)
    
    threads = [threading.Thread(target=build_category_page, args=(category, items)) for category, items in data.items()]
    [t.start() for t in threads]
    [t.join() for t in threads]


if __name__ == '__main__':
    notion_duolingo()

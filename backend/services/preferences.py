import json
from pathlib import Path
import config

def load_preferences():
    path = Path(config.DATA_DIR) / 'preferences.json'
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
        language = values.get('language')
        if language in {'en', 'de'}:
            config.UI_LANGUAGE = language
            return {'language': language}
    except (OSError, ValueError, AttributeError):
        pass
    return {}

def save_preferences(language):
    if language not in {'en', 'de'}:
        raise ValueError('LANGUAGE_UNSUPPORTED')
    path = Path(config.DATA_DIR) / 'preferences.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'language': language}), encoding='utf-8')
    temporary.replace(path)
    config.UI_LANGUAGE = language
    return {'language': language}

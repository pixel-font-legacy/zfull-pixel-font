from typing import Literal, get_args

type LanguageFlavor = Literal[
    'gb',
    'big5',
]
language_flavors = list[LanguageFlavor](get_args(LanguageFlavor.__value__))

type FontFormat = Literal[
    'otf',
    'otf.woff',
    'otf.woff2',
    'ttf',
    'ttf.woff',
    'ttf.woff2',
    'ms.bitmap.ttf',
    'otb',
    'dfont',
    'bdf',
    'pcf',
]
font_formats = list[FontFormat](get_args(FontFormat.__value__))

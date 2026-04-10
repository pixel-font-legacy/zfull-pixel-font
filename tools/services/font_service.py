import itertools
from datetime import datetime

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.BitmapGlyphMetrics import SmallGlyphMetrics, BigGlyphMetrics
from fontTools.ttLib.tables.E_B_D_T_ import table_E_B_D_T_, ebdt_bitmap_classes, ebdt_bitmap_format_5, ebdt_bitmap_format_8, ebdt_bitmap_format_9
from fontTools.ttLib.tables.E_B_L_C_ import table_E_B_L_C_
# noinspection PyProtectedMember
from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
from loguru import logger
from pixel_font_builder import FontBuilder, Glyph, WeightName, SerifStyle, SlantStyle, WidthStyle, opentype

from tools import configs
from tools.configs import path_define, options
from tools.configs.options import LanguageFlavor, FontFormat


def dump_fonts(font_formats: list[FontFormat]) -> dict[LanguageFlavor, list[int]]:
    path_define.outputs_dir.mkdir(parents=True, exist_ok=True)

    dump_logs = {}
    for language_flavor in options.language_flavors:
        tt_font = TTFont(path_define.fonts_dir.joinpath(f'Zfull-{language_flavor.upper()}.ttf'))
        tb_name: table__n_a_m_e = tt_font['name']
        tb_eblc: table_E_B_L_C_ = tt_font['EBLC']
        tb_ebdt: table_E_B_D_T_ = tt_font['EBDT']

        font_sizes = []

        for strike, strike_data in zip(tb_eblc.strikes, tb_ebdt.strikeData):
            assert strike.bitmapSizeTable.ppemX == strike.bitmapSizeTable.ppemY
            assert strike.bitmapSizeTable.bitDepth == 1

            builder = FontBuilder()

            builder.font_metric.font_size = strike.bitmapSizeTable.ppemY
            builder.font_metric.horizontal_layout.ascent = strike.bitmapSizeTable.hori.ascender
            builder.font_metric.horizontal_layout.descent = strike.bitmapSizeTable.hori.descender
            builder.font_metric.vertical_layout.ascent = strike.bitmapSizeTable.vert.ascender
            builder.font_metric.vertical_layout.descent = strike.bitmapSizeTable.vert.descender

            builder.meta_info.version = f'{tb_name.getDebugName(5)} - Dump {configs.version}'
            builder.meta_info.created_time = datetime.fromisoformat(f'{configs.version.replace('.', '-')}T00:00:00Z')
            builder.meta_info.modified_time = builder.meta_info.created_time
            builder.meta_info.family_name = f'{tb_name.getDebugName(1)} {builder.font_metric.font_size}px'
            builder.meta_info.weight_name = WeightName.REGULAR
            builder.meta_info.serif_style = SerifStyle.SERIF
            builder.meta_info.slant_style = SlantStyle.NORMAL
            builder.meta_info.width_style = WidthStyle.PROPORTIONAL
            builder.meta_info.copyright_info = tb_name.getDebugName(0)

            glyph_infos = {}
            for index_sub_table in strike.indexSubTables:
                for glyph_name in index_sub_table.names:
                    assert glyph_name not in glyph_infos
                    bitmap_data = strike_data[glyph_name]
                    assert isinstance(bitmap_data, ebdt_bitmap_classes[index_sub_table.imageFormat])

                    if isinstance(bitmap_data, ebdt_bitmap_format_5):
                        metrics = index_sub_table.metrics
                    else:
                        metrics = bitmap_data.metrics

                    assert not isinstance(bitmap_data, (ebdt_bitmap_format_8, ebdt_bitmap_format_9))
                    bitmap = []
                    for row_n in range(metrics.height):
                        row_bytes = bitmap_data.getRow(row_n, bitDepth=strike.bitmapSizeTable.bitDepth, metrics=metrics)
                        row_string = ''
                        for b in row_bytes:
                            row_string += f'{b:08b}'
                        bitmap.append([int(c) for c in row_string])

                    glyph_infos[glyph_name] = {
                        'metrics': metrics,
                        'bitmap': bitmap,
                    }

            bitmap_y_offset = configs.bitmap_y_offsets.get(builder.font_metric.font_size, 0)

            glyph_names = set()
            for code_point, glyph_name in sorted(itertools.chain([(-1, '.notdef')], tt_font.getBestCmap().items())):
                if glyph_name not in glyph_infos and glyph_name != '.notdef':
                    continue

                if code_point != -1:
                    builder.character_mapping[code_point] = glyph_name

                if glyph_name in glyph_names:
                    continue
                glyph_names.add(glyph_name)

                if glyph_name not in glyph_infos:
                    assert glyph_name == '.notdef'
                    builder.glyphs.append(Glyph(
                        name='.notdef',
                        advance_width=builder.font_metric.font_size,
                        advance_height=builder.font_metric.font_size,
                    ))
                    continue

                glyph_info = glyph_infos[glyph_name]
                metrics = glyph_info['metrics']

                if isinstance(metrics, SmallGlyphMetrics):
                    if strike.bitmapSizeTable.flags == 1:  # Horizontal
                        hori_bearing_x = metrics.BearingX
                        hori_bearing_y = metrics.BearingY
                        hori_advance = metrics.Advance
                        vert_bearing_x = 0
                        vert_bearing_y = 0
                        vert_advance = 0
                    else:  # Vertical
                        assert strike.bitmapSizeTable.flags == 2
                        hori_bearing_x = 0
                        hori_bearing_y = 0
                        hori_advance = 0
                        vert_bearing_x = metrics.BearingX
                        vert_bearing_y = metrics.BearingY
                        vert_advance = metrics.Advance
                else:
                    assert isinstance(metrics, BigGlyphMetrics)
                    hori_bearing_x = metrics.horiBearingX
                    hori_bearing_y = metrics.horiBearingY
                    hori_advance = metrics.horiAdvance
                    vert_bearing_x = metrics.vertBearingX
                    vert_bearing_y = metrics.vertBearingY
                    vert_advance = metrics.vertAdvance

                bitmap = glyph_info['bitmap']
                assert bitmap is not None

                builder.glyphs.append(Glyph(
                    name=glyph_name,
                    horizontal_offset=(hori_bearing_x, hori_bearing_y - metrics.height + bitmap_y_offset),
                    advance_width=hori_advance,
                    vertical_offset=(vert_bearing_x, vert_bearing_y - bitmap_y_offset),
                    advance_height=vert_advance,
                    bitmap=bitmap,
                ))

            for font_format in font_formats:
                file_path = path_define.outputs_dir.joinpath(f'Zfull-{language_flavor.upper()}-{builder.font_metric.font_size}px.{font_format}')
                match font_format:
                    case 'otf.woff':
                        builder.save_otf(file_path, flavor=opentype.Flavor.WOFF)
                    case 'otf.woff2':
                        builder.save_otf(file_path, flavor=opentype.Flavor.WOFF2)
                    case 'ttf.woff':
                        builder.save_ttf(file_path, flavor=opentype.Flavor.WOFF)
                    case 'ttf.woff2':
                        builder.save_ttf(file_path, flavor=opentype.Flavor.WOFF2)
                    case _:
                        getattr(builder, f'save_{font_format}')(file_path)
                logger.info("Make font: '{}'", file_path)

            font_sizes.append(builder.font_metric.font_size)

        font_sizes.sort()
        dump_logs[language_flavor] = font_sizes
    return dump_logs

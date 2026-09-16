from __future__ import annotations

from dataclasses import dataclass
import math

from .models import Action
from .dom_inspector import SiteAnalysis, SiteElement


@dataclass(frozen=True)
class TourOptions:
    reload_before: bool = True
    has_intro_animation: bool = True
    intro_wait: float = 2.5
    include_sections: bool = True
    include_ctas: bool = True
    click_safe_ctas: bool = False
    camera_focus: bool = True
    add_pauses: bool = True
    max_points: int = 16
    transition: str = "zoom"


def _even_sample(items: list[SiteElement], count: int) -> list[SiteElement]:
    if count <= 0 or not items:
        return []
    if len(items) <= count:
        return items[:]
    if count == 1:
        return [max(items, key=lambda x: x.score)]

    # Divide verticalmente a página e prefere o elemento mais relevante em cada faixa.
    ordered = sorted(items, key=lambda x: x.doc_y)
    result: list[SiteElement] = []
    for i in range(count):
        lo = math.floor(i * len(ordered) / count)
        hi = max(lo + 1, math.floor((i + 1) * len(ordered) / count))
        chunk = ordered[lo:hi]
        result.append(max(chunk, key=lambda x: x.score))
    return result


def _dedupe_nearby(items: list[SiteElement], min_gap: float = 85.0) -> list[SiteElement]:
    result: list[SiteElement] = []
    for item in sorted(items, key=lambda x: x.doc_y):
        if any(item.selector == x.selector for x in result):
            continue
        # Mantém CTAs junto de um título se forem de tipos diferentes; remove só duplicatas visuais muito próximas do mesmo tipo.
        near = next((x for x in reversed(result[-3:]) if abs(item.doc_y - x.doc_y) < min_gap and item.kind == x.kind), None)
        if near is not None:
            if item.score > near.score:
                result[result.index(near)] = item
            continue
        result.append(item)
    return sorted(result, key=lambda x: x.doc_y)


def select_tour_elements(analysis: SiteAnalysis, options: TourOptions) -> list[SiteElement]:
    max_points = max(4, min(30, int(options.max_points)))
    structural_kinds = {"heading", "section", "main", "footer"}
    interactive_kinds = {"button", "link"}

    structural = [x for x in analysis.elements if options.include_sections and x.kind in structural_kinds]
    interactive = [x for x in analysis.elements if options.include_ctas and x.kind in interactive_kinds and x.label]

    # Títulos são mais úteis do que containers gigantes quando ambos apontam para a mesma área.
    structural = sorted(structural, key=lambda x: (x.doc_y, -x.score))
    structural = _dedupe_nearby(structural, 120.0)
    interactive = _dedupe_nearby(interactive, 70.0)

    if structural and interactive:
        section_quota = max(2, round(max_points * 0.65))
        cta_quota = max_points - section_quota
    elif structural:
        section_quota, cta_quota = max_points, 0
    else:
        section_quota, cta_quota = 0, max_points

    chosen = _even_sample(structural, section_quota) + _even_sample(interactive, cta_quota)
    chosen = _dedupe_nearby(chosen, 55.0)
    if len(chosen) > max_points:
        chosen = _even_sample(chosen, max_points)
    return sorted(chosen, key=lambda x: x.doc_y)


def build_tour_actions(analysis: SiteAnalysis, options: TourOptions) -> list[Action]:
    actions: list[Action] = []

    if options.reload_before:
        wait_after_reload = max(0.8, float(options.intro_wait if options.has_intro_animation else 1.2))
        actions.append(Action(
            type="reload",
            name="Recarregar página + entrada" if options.has_intro_animation else "Recarregar página",
            duration=wait_after_reload,
            pause_after=0.0,
        ))

    points = select_tour_elements(analysis, options)
    if not points:
        # Fallback previsível caso o site tenha HTML pouco semântico.
        actions.extend([
            Action(type="wait", name="Pausa inicial", duration=0.7, pause_after=0.0),
            Action(type="scroll", name="Scroll automático 1", amount=-7, duration=1.35),
            Action(type="scroll", name="Scroll automático 2", amount=-7, duration=1.45),
            Action(type="scroll", name="Scroll automático 3", amount=-7, duration=1.35),
        ])
        return actions

    for idx, point in enumerate(points, start=1):
        label = point.label or point.kind
        if len(label) > 42:
            label = label[:39] + "…"
        is_interactive = point.kind in {"button", "link"}
        actions.append(Action(
            type="dom_visit",
            name=f"Auto {idx:02d} · {label}",
            duration=0.72 if options.add_pauses else 0.35,
            transition=options.transition,
            zoom=1.13 if options.camera_focus else 1.0,
            pause_after=0.18 if options.add_pauses else 0.02,
            selector=point.selector,
            element_label=point.label,
            element_kind=point.kind,
            auto_click=bool(options.click_safe_ctas and is_interactive and point.safe_click),
            settle=0.40,
        ))

    if options.add_pauses:
        actions.append(Action(type="wait", name="Fechamento", duration=0.55, pause_after=0.0))
    return actions


@dataclass(frozen=True)
class FullPageScrollOptions:
    """Preset cinematográfico para mostrar a página inteira do topo ao rodapé."""
    start_pause: float = 0.75
    end_pause: float = 0.85
    overlap_ratio: float = 0.18
    target_speed_px_s: float = 470.0
    min_segment_duration: float = 1.20
    max_segment_duration: float = 2.85
    pause_between: float = 0.12


def build_full_page_scroll_tour(
    analysis: SiteAnalysis,
    options: FullPageScrollOptions | None = None,
) -> list[Action]:
    """Cria scrolls exatos de documento cobrindo a página inteira.

    O stride mantém uma pequena sobreposição visual entre "telas". O movimento
    entre os alvos é contínuo, então todo o conteúdo intermediário também entra
    na gravação. A duração é calculada pela distância para manter velocidade
    visual consistente em páginas curtas e longas.
    """
    opt = options or FullPageScrollOptions()
    doc_h = max(0.0, float(analysis.doc_height))
    viewport_h = max(320.0, float(analysis.viewport_height or 800))
    max_scroll = max(0.0, doc_h - viewport_h)

    actions: list[Action] = [
        Action(
            type="wait",
            name="Abertura · página inteira",
            duration=max(0.25, float(opt.start_pause)),
            pause_after=0.0,
            doc_height=doc_h,
            viewport_height=viewport_h,
            page_url=analysis.url,
        )
    ]

    if max_scroll <= 8.0:
        actions.append(Action(
            type="wait",
            name="Página já cabe inteira na tela",
            duration=max(0.45, float(opt.end_pause)),
            pause_after=0.0,
            doc_height=doc_h,
            viewport_height=viewport_h,
            page_url=analysis.url,
        ))
        return actions

    overlap = max(0.08, min(0.35, float(opt.overlap_ratio)))
    # ~82% de uma viewport por trecho: deixa contexto visual sobreposto e
    # evita "pular" seções, mas sem tornar o vídeo excessivamente longo.
    desired_stride = viewport_h * (1.0 - overlap)
    desired_stride = max(360.0, min(1100.0, desired_stride))
    segments = max(1, int(math.ceil(max_scroll / desired_stride)))

    # Em páginas enormes, evita centenas de paradas. O scroll continua
    # mostrando todos os pixels entre os pontos, então aumentar o stride não
    # cria buracos na gravação.
    segments = min(32, segments)
    actual_stride = max_scroll / segments

    source = 0.0
    for i in range(1, segments + 1):
        target = max_scroll if i == segments else min(max_scroll, actual_stride * i)
        distance = abs(target - source)

        # Tempo proporcional à distância, com limites cinematográficos.
        duration = distance / max(260.0, float(opt.target_speed_px_s))
        duration += 0.20  # respiro de easing no início/fim de cada trecho
        duration = max(float(opt.min_segment_duration), min(float(opt.max_segment_duration), duration))

        actions.append(Action(
            type="site_scroll",
            name=f"Página inteira · trecho {i:02d}/{segments:02d}",
            duration=duration,
            pause_after=float(opt.pause_between) if i < segments else 0.0,
            target_scroll_y=target,
            capture_scroll_y=source,
            viewport_height=viewport_h,
            doc_height=doc_h,
            page_url=analysis.url,
        ))
        source = target

    actions.append(Action(
        type="wait",
        name="Fechamento · rodapé",
        duration=max(0.35, float(opt.end_pause)),
        pause_after=0.0,
        target_scroll_y=max_scroll,
        capture_scroll_y=max_scroll,
        viewport_height=viewport_h,
        doc_height=doc_h,
        page_url=analysis.url,
    ))
    return actions

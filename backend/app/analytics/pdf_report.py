"""
PDF Report Generator — CryptoTradeHub (PEND-08)
================================================

Generates professional PDF reports using ReportLab:
  1. Performance report — monthly metrics per bot
  2. Fiscal report — gains summary for tax declaration
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Brand constants ──────────────────────────────────────────────────────────

APP_NAME = "Pro Trader-EA"
APP_SUBTITLE = "Crypto Trade Hub"
BRAND_COLOR = colors.HexColor("#0ea5e9")   # cyan-500
BRAND_DARK = colors.HexColor("#0c4a6e")    # cyan-900
HEADER_BG = colors.HexColor("#0f172a")     # slate-900
ROW_ALT = colors.HexColor("#f1f5f9")       # slate-100

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


# ── Helpers ──────────────────────────────────────────────────────────────────

def _styles():
    """Build custom paragraph styles."""
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        "BrandTitle",
        parent=ss["Title"],
        fontSize=20,
        textColor=BRAND_COLOR,
        spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        "BrandSubtitle",
        parent=ss["Normal"],
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=14,
    ))
    ss.add(ParagraphStyle(
        "SectionHead",
        parent=ss["Heading2"],
        fontSize=13,
        textColor=BRAND_DARK,
        spaceBefore=16,
        spaceAfter=8,
    ))
    ss.add(ParagraphStyle(
        "SmallGray",
        parent=ss["Normal"],
        fontSize=8,
        textColor=colors.gray,
    ))
    return ss


def _header_block(title: str, subtitle: str, ss) -> list:
    """Branded report header."""
    return [
        Paragraph(f"<b>{APP_NAME}</b>", ss["BrandTitle"]),
        Paragraph(subtitle, ss["BrandSubtitle"]),
        Paragraph(f"<b>{title}</b>", ss["Heading1"]),
        Spacer(1, 6 * mm),
    ]


def _footer(canvas, doc):
    """Page footer with branding and page number."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.gray)
    canvas.drawString(
        MARGIN,
        15 * mm,
        f"{APP_NAME} — {APP_SUBTITLE}  |  Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    )
    canvas.drawRightString(
        PAGE_W - MARGIN,
        15 * mm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def _metric_table(rows: List[List[str]], col_widths: Optional[list] = None) -> Table:
    """Two-column metric table (label / value)."""
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(style)
    return t


def _trades_table(trades: List[Dict[str, Any]]) -> Table:
    """Full trades table with coloured PnL."""
    header = ["Data", "Bot", "Símbolo", "Lado", "Preço", "Qtd", "Total", "PnL", "Status"]
    data = [header]

    for t in trades:
        created = t.get("created_at", "")
        if isinstance(created, datetime):
            created = created.strftime("%Y-%m-%d %H:%M")
        pnl = t.get("pnl", 0) or 0
        pnl_str = f"{pnl:+.2f}" if isinstance(pnl, (int, float)) else str(pnl)
        data.append([
            str(created),
            str(t.get("bot_id", ""))[:12],
            str(t.get("symbol", "")),
            str(t.get("side", "")),
            f"{float(t.get('price', 0)):.4f}" if t.get("price") else "",
            f"{float(t.get('quantity', 0)):.6f}" if t.get("quantity") else "",
            f"{float(t.get('total_usdt', 0)):.2f}" if t.get("total_usdt") else "",
            pnl_str,
            str(t.get("status", "")),
        ])

    col_w = [60, 55, 55, 30, 52, 50, 50, 48, 42]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    # Color PnL cells
    for i in range(1, len(data)):
        pnl_val = trades[i - 1].get("pnl", 0) or 0
        if isinstance(pnl_val, (int, float)):
            if pnl_val > 0:
                style_cmds.append(("TEXTCOLOR", (7, i), (7, i), colors.HexColor("#16a34a")))
            elif pnl_val < 0:
                style_cmds.append(("TEXTCOLOR", (7, i), (7, i), colors.HexColor("#dc2626")))

    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


# ── Public API ───────────────────────────────────────────────────────────────

def generate_performance_pdf(
    *,
    user_email: str,
    trades: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    bots: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bytes:
    """Generate monthly performance report PDF.

    Returns the raw PDF bytes (ready to be sent in a StreamingResponse).
    """
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    elements: list = []

    # ── Header
    period = ""
    if start_date and end_date:
        period = f"Período: {start_date} — {end_date}"
    elif start_date:
        period = f"A partir de {start_date}"
    elif end_date:
        period = f"Até {end_date}"
    else:
        period = f"Todos os trades — gerado em {datetime.utcnow().strftime('%Y-%m-%d')}"

    elements.extend(_header_block("Relatório de Performance", period, ss))
    elements.append(Paragraph(f"Usuário: {user_email}", ss["SmallGray"]))
    elements.append(Spacer(1, 4 * mm))

    # ── Key metrics table
    elements.append(Paragraph("Métricas Gerais", ss["SectionHead"]))

    metric_rows = [
        ["Métrica", "Valor"],
        ["Total P&L", f"${metrics.get('total_pnl', 0):,.2f}"],
        ["Retorno Total (%)", f"{metrics.get('total_return_pct', 0):.2f}%"],
        ["Retorno Anualizado (%)", f"{metrics.get('annualized_return_pct', 0):.2f}%"],
        ["Nº de Trades", str(metrics.get("num_trades", 0))],
        ["Win Rate", f"{metrics.get('win_rate', 0):.1f}%"],
        ["Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"],
        ["Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}"],
        ["Max Drawdown (%)", f"{metrics.get('max_drawdown_pct', 0):.2f}%"],
        ["Max Drawdown (abs)", f"${metrics.get('max_drawdown_abs', 0):,.2f}"],
        ["Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}"],
        ["Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"],
        ["Melhor Trade", f"${metrics.get('best_trade', 0):,.2f}"],
        ["Pior Trade", f"${metrics.get('worst_trade', 0):,.2f}"],
        ["Ganho Médio", f"${metrics.get('avg_win', 0):,.2f}"],
        ["Perda Média", f"${metrics.get('avg_loss', 0):,.2f}"],
        ["Duração Média (h)", f"{metrics.get('avg_trade_duration_hours', 0):.1f}"],
        ["Dias de Trading", str(metrics.get("trading_days", 0))],
    ]
    elements.append(_metric_table(metric_rows, col_widths=[180, 180]))
    elements.append(Spacer(1, 6 * mm))

    # ── Bot comparison (if multiple bots)
    if bots and len(bots) > 0:
        elements.append(Paragraph("Comparativo por Bot", ss["SectionHead"]))
        bot_header = ["Bot ID", "Símbolo", "Trades", "P&L", "Win Rate", "Retorno %"]
        bot_rows = [bot_header]
        for b in bots:
            bot_rows.append([
                str(b.get("bot_id", ""))[:16],
                str(b.get("symbol", "")),
                str(b.get("num_trades", 0)),
                f"${b.get('total_pnl', 0):,.2f}",
                f"{b.get('win_rate', 0):.1f}%",
                f"{b.get('total_return_pct', 0):.2f}%",
            ])
        elements.append(_metric_table(bot_rows, col_widths=[80, 65, 45, 65, 55, 55]))
        elements.append(Spacer(1, 6 * mm))

    # ── Trades table
    if trades:
        elements.append(Paragraph(f"Histórico de Trades ({len(trades)} registros)", ss["SectionHead"]))
        elements.append(_trades_table(trades[:500]))  # cap at 500 in PDF

    # Build
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def generate_fiscal_pdf(
    *,
    user_email: str,
    trades: List[Dict[str, Any]],
    year: int,
) -> bytes:
    """Generate fiscal / tax report PDF for a given year.

    Groups trades by month and calculates total gains/losses.
    Returns the raw PDF bytes.
    """
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    elements: list = []

    # ── Header
    elements.extend(
        _header_block(
            "Relatório Fiscal de Ganhos",
            f"Ano-calendário: {year}  |  Gerado em {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            ss,
        )
    )
    elements.append(Paragraph(f"Usuário: {user_email}", ss["SmallGray"]))
    elements.append(Spacer(1, 4 * mm))

    # ── Group by month
    monthly: Dict[int, Dict[str, float]] = {}
    for m in range(1, 13):
        monthly[m] = {"gains": 0.0, "losses": 0.0, "count": 0}

    total_gains = 0.0
    total_losses = 0.0
    total_count = 0

    for t in trades:
        pnl = t.get("pnl")
        if pnl is None:
            continue
        try:
            pnl = float(pnl)
        except (TypeError, ValueError):
            continue
        created = t.get("created_at")
        if isinstance(created, datetime):
            m = created.month
        else:
            continue
        monthly[m]["count"] += 1
        total_count += 1
        if pnl >= 0:
            monthly[m]["gains"] += pnl
            total_gains += pnl
        else:
            monthly[m]["losses"] += pnl
            total_losses += pnl

    # ── Monthly summary table
    elements.append(Paragraph("Resumo Mensal", ss["SectionHead"]))
    month_names = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]

    table_data = [["Mês", "Operações", "Ganhos (USDT)", "Perdas (USDT)", "Líquido (USDT)"]]
    for m in range(1, 13):
        d = monthly[m]
        net = d["gains"] + d["losses"]
        table_data.append([
            month_names[m],
            str(d["count"]),
            f"${d['gains']:,.2f}",
            f"${d['losses']:,.2f}",
            f"${net:+,.2f}",
        ])

    # Totals row
    total_net = total_gains + total_losses
    table_data.append([
        "TOTAL",
        str(total_count),
        f"${total_gains:,.2f}",
        f"${total_losses:,.2f}",
        f"${total_net:+,.2f}",
    ])

    col_w = [75, 60, 85, 85, 85]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # Bold total row
        ("BACKGROUND", (0, -1), (-1, -1), BRAND_DARK),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]

    # Color net values
    for i in range(1, len(table_data) - 1):
        net_val = monthly[i]["gains"] + monthly[i]["losses"]
        if net_val > 0:
            style_cmds.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#16a34a")))
        elif net_val < 0:
            style_cmds.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#dc2626")))

    t = Table(table_data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 8 * mm))

    # ── Annual summary box
    elements.append(Paragraph("Resumo Anual", ss["SectionHead"]))
    annual_rows = [
        ["Descrição", "Valor (USDT)"],
        ["Total de Operações", str(total_count)],
        ["Total de Ganhos", f"${total_gains:,.2f}"],
        ["Total de Perdas", f"${total_losses:,.2f}"],
        ["Resultado Líquido", f"${total_net:+,.2f}"],
    ]
    elements.append(_metric_table(annual_rows, col_widths=[200, 160]))
    elements.append(Spacer(1, 8 * mm))

    # ── Disclaimer
    elements.append(Paragraph(
        "<i>Este relatório é gerado automaticamente para fins informativos. "
        "Consulte um contador para orientação fiscal oficial. "
        "Valores em USDT (Tether). A conversão para moeda local deve considerar a taxa "
        "de câmbio vigente na data de cada operação.</i>",
        ss["SmallGray"],
    ))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

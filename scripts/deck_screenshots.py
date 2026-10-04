"""Screenshots of the PS 26086 app for the submission deck (app served at http://localhost:8766).

  python scripts/deck_screenshots.py  -> docs/deck_assets/*.png
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "deck_assets"
URL = "http://localhost:8766/"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


async def tab(page, name):
    view = {"Risk map": "map", "Officer": "officer", "Model": "model", "Panchayat": "panchayat"}[name]
    await page.locator(f'button.tab[data-view="{view}"]').click()
    await page.wait_for_timeout(1800)


async def shot_el(page, selector, path, pad_top=0):
    el = page.locator(selector).first
    await el.scroll_into_view_if_needed()
    await page.wait_for_timeout(500)
    await el.screenshot(path=str(OUT / path))


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        page = await b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        await page.goto(URL); await page.wait_for_timeout(3000)
        await page.screenshot(path=str(OUT / "01_panchayat_full.png"))
        await tab(page, "Risk map"); await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "02_risk_map.png"))
        await tab(page, "Officer")
        await page.screenshot(path=str(OUT / "03_officer.png"))
        await tab(page, "Model")
        await shot_el(page, "#pipeline", "04_pipeline.png")
        await shot_el(page, "#can-cannot", "05_can_cannot.png")
        await shot_el(page, "#skill-chart", "06_skill_by_lead.png")
        await shot_el(page, "#rel-grid", "07_reliability_grid.png")
        await shot_el(page, "#sel-table", "08_shipped_table.png")
        # Kannada panchayat card on a phone
        m = await b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True)
        await m.goto(URL); await m.wait_for_timeout(3000)
        await m.locator("#btn-lang").click(); await m.wait_for_timeout(1500)
        await m.screenshot(path=str(OUT / "09_mobile_kannada.png"), full_page=False)
        await m.screenshot(path=str(OUT / "10_mobile_kannada_long.png"), clip={"x": 0, "y": 0, "width": 390, "height": 1500}, full_page=True)
        await b.close()
    print("\n".join(sorted(x.name for x in OUT.glob("*.png"))))


asyncio.run(main())

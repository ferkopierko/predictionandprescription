"""Navigácia a spoločný vzhľad pracovného priestoru HronTech."""
from pathlib import Path
import streamlit as st

PAGES = {
    'Firma': ('HronTech Strojárne', '', ''),
    'Simulácia': ('Incidenty', '', ''),
    'Živé sledovanie': ('Živé sledovanie', '', ''),
    'Nové hodnotenie': ('Nové hodnotenie', '', ''),
    'Uložené hodnotenia': ('Hodnotenia', '', ''),
    'Prehľad': ('Prehľad', '', ''),
    'Register rizík': ('Plán ochrany', '', ''),
    'Predpoklady': ('Nastavenia', '', ''),
}
SECTIONS = {
    'Firma': 'Firma', 'Incidenty': 'Simulácia', 'Hodnotenia': 'Uložené hodnotenia',
    'Prehľad': 'Prehľad', 'Ochrana': 'Register rizík', 'Nastavenia': 'Predpoklady',
}
PAGE_SECTION = {page: section for section, page in SECTIONS.items()}
PAGE_SECTION.update({'Živé sledovanie': 'Incidenty', 'Nové hodnotenie': 'Hodnotenia'})
VIEWS = {
    'Incidenty': {'Scenáre': 'Simulácia', 'Živé sledovanie': 'Živé sledovanie'},
    'Hodnotenia': {'História': 'Uložené hodnotenia', 'Nové hodnotenie': 'Nové hodnotenie'},
}

def apply_style():
    st.html('<style>' + (Path(__file__).parent/'static/interface.css').read_text(encoding='utf-8') + '</style>')

def shell():
    for key in list(st.session_state):
        if key.startswith(('f_', 'company_')) or key in {'frekvencia','rozpocet','register_view','history_search','history_impact','intake_step'}:
            st.session_state[key] = st.session_state[key]
    page = st.session_state.get('workspace_page', 'Firma')
    if page not in PAGES:
        page = 'Firma'
    external = page != st.session_state.get('_previous_page')
    if external:
        st.session_state['main_nav'] = PAGE_SECTION[page]
    with st.sidebar:
        st.html('<div class="atlas-brand">HronTech<span>Strojárne</span></div>')
        section = st.radio('Pracovný priestor', list(SECTIONS), key='main_nav', label_visibility='collapsed')
    if section != PAGE_SECTION[page]:
        page = SECTIONS[section]
        external = True
    heading = st.empty()
    if section in VIEWS:
        views = VIEWS[section]
        key = 'view_' + section
        if external or key not in st.session_state:
            st.session_state[key] = next(label for label, value in views.items() if value == page)
        chosen = st.segmented_control('Zobrazenie', list(views), key=key, label_visibility='collapsed')
        page = views[chosen or next(iter(views))]
    st.session_state['workspace_page'] = page
    st.session_state['_previous_page'] = page
    title = 'Výsledok hodnotenia' if page == 'Nové hodnotenie' and 'vysledok' in st.session_state else PAGES[page][0]
    heading.html(f'<header class="atlas-page-header"><h1>{title}</h1></header>')
    return page

def footer():
    pass

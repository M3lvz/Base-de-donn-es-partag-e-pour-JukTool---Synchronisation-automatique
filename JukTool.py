# ToolSorter – Streamlit app (version avec pages détaillées)
# ------------------------------------------------------------
# Fonctionnalités :
# - Ajouter des outils avec enrichissement IA optionnel
# - Recherche intelligente avec RapidFuzz
# - Import/export JSON fonctionnel
# - Configuration OpenAI
# - Pages détaillées pour chaque outil avec chat et liens
# ------------------------------------------------------------
# Démarrage : streamlit run JukTool.py
# ------------------------------------------------------------

import os
import io
import json
import hashlib
import subprocess
import threading
import time
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st
from rapidfuzz import fuzz
from duckduckgo_search import DDGS

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# === Configuration ===
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "tools.json")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
COMMENTS_PATH = os.path.join(DATA_DIR, "comments.json")
LINKS_PATH = os.path.join(DATA_DIR, "external_links.json")
os.makedirs(DATA_DIR, exist_ok=True)

# === Streamlit config ===
st.set_page_config(page_title="ToolSorter", layout="wide")
st.title("🧰 ToolSorter – Gestionnaire d'outils IA")
st.caption("Ajoute, importe, cherche tes outils. Simple et efficace.")

# === Fonctions utilitaires ===
DEFAULT_DB = {"tools": []}
DEFAULT_COMMENTS = {}
DEFAULT_LINKS = {}

def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        save_db(DEFAULT_DB)
        return DEFAULT_DB.copy()
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DB.copy()

def save_db(db: Dict[str, Any]) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    # Synchronisation automatique avec GitHub si activée
    if st.session_state.get("auto_sync_enabled", False):
        try:
            # Synchronisation en arrière-plan
            sync_thread = threading.Thread(target=lambda: git_sync_to_github(), daemon=True)
            sync_thread.start()
        except Exception:
            pass  # Ignorer les erreurs de sync pour ne pas bloquer la sauvegarde

def load_comments() -> Dict[str, Any]:
    if not os.path.exists(COMMENTS_PATH):
        save_comments(DEFAULT_COMMENTS)
        return DEFAULT_COMMENTS.copy()
    try:
        with open(COMMENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_COMMENTS.copy()

def save_comments(comments: Dict[str, Any]) -> None:
    with open(COMMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
    
    # Synchronisation automatique avec GitHub si activée
    if st.session_state.get("auto_sync_enabled", False):
        try:
            # Synchronisation en arrière-plan
            sync_thread = threading.Thread(target=lambda: git_sync_to_github(), daemon=True)
            sync_thread.start()
        except Exception:
            pass  # Ignorer les erreurs de sync pour ne pas bloquer la sauvegarde

def load_links() -> Dict[str, Any]:
    if not os.path.exists(LINKS_PATH):
        save_links(DEFAULT_LINKS)
        return DEFAULT_LINKS.copy()
    try:
        with open(LINKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_LINKS.copy()

def save_links(links: Dict[str, Any]) -> None:
    with open(LINKS_PATH, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)
    
    # Synchronisation automatique avec GitHub si activée
    if st.session_state.get("auto_sync_enabled", False):
        try:
            # Synchronisation en arrière-plan
            sync_thread = threading.Thread(target=lambda: git_sync_to_github(), daemon=True)
            sync_thread.start()
        except Exception:
            pass  # Ignorer les erreurs de sync pour ne pas bloquer la sauvegarde

def normalize_kw(s: str) -> List[str]:
    if not s:
        return []
    parts = [p.strip().lower() for p in s.replace(",", ";").split(";")]
    return [p for p in parts if p]

def euros(n: int) -> str:
    try:
        n = max(1, min(5, int(n)))
    except Exception:
        n = 3
    return "💶" * n

def tool_id(obj: Dict[str, Any]) -> str:
    payload = (obj.get("name", "") + "|" + obj.get("link", "")).strip().lower()
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

def dedupe_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for t in tools:
        tid = t.get("id") or tool_id(t)
        if tid not in seen:
            seen.add(tid)
            t["id"] = tid
            out.append(t)
    return out

# === Configuration OpenAI ===
DEFAULT_CONFIG = {
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini"
}

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_api_key() -> str:
    env = os.getenv("OPENAI_API_KEY", "")
    cfg = load_config()
    return (cfg.get("openai_api_key") or env or "").strip()

def have_openai() -> bool:
    return bool(get_api_key()) and (OpenAI is not None)

def get_openai_client():
    if not have_openai():
        return None
    return OpenAI(api_key=get_api_key())

# === Recherche web ===
def ddg_snippets(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
    except Exception:
        pass
    return results

# === IA OpenAI ===
def ai_enrich(tool: Dict[str, Any]) -> Dict[str, Any]:
    client = get_openai_client()
    if not client:
        return {**tool, "ai_enriched": False, "ai_note": "OpenAI non configuré"}
    
    try:
        # Recherche web pour enrichir l'analyse
        web_results = ddg_snippets(tool.get("name", "") + " " + tool.get("link", ""), max_results=5)
        web_context = ""
        if web_results:
            web_context = "\n\nInformations web trouvées:\n" + "\n".join([
                f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}..."
                for r in web_results
            ])
        
        prompt = f"""Tu es un expert en référencement d'outils IA. Analyse cet outil et enrichis-le de manière exhaustive.

OUTIL À ANALYSER:
{json.dumps(tool, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
1. Garde TOUS les champs existants (name, link, description, category, keywords, price_euros_1_to_5)
2. Améliore la description pour qu'elle soit précise et complète
3. Analyse TOUS les angles d'usage possibles de cet outil
4. Génère jusqu'à 20 mots-clés pertinents et variés
5. Catégorise de manière précise

EXEMPLES D'ANGLES À EXPLORER:
- ChatGPT: chatbot, génération texte, agent IA, assistant virtuel, analyse de données, tutorat, rédaction, traduction, brainstorming, planification, etc.
- Midjourney: génération d'images, art numérique, design, illustration, concept art, marketing visuel, etc.

Réponds STRICTEMENT en JSON avec:
{{
    "description": "Description améliorée et précise",
    "keywords": ["mot-clé1", "mot-clé2", "mot-clé3", ...],
    "category": "Catégorie précise et détaillée"
}}

{web_context}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # Normaliser les mots-clés
        keywords = data.get("keywords", [])
        if isinstance(keywords, list):
            # Nettoyer et limiter à 20 mots-clés
            clean_keywords = []
            for kw in keywords[:20]:
                if isinstance(kw, str) and kw.strip():
                    clean_keywords.append(kw.strip().lower())
            keywords = clean_keywords
        
        return {
            **tool,
            "description": data.get("description", tool.get("description", "")),
            "keywords": keywords,
            "category": data.get("category", tool.get("category", "")),
            "ai_enriched": True,
            "ai_note": "Enrichi par IA avec recherche web"
        }
    except Exception as e:
        return {**tool, "ai_enriched": False, "ai_note": f"Erreur IA: {e}"}

# === Gestion des commentaires ===
def add_comment(tool_id: str, author: str, content: str, rating: int = 0) -> None:
    comments = load_comments()
    if tool_id not in comments:
        comments[tool_id] = []
    
    comment = {
        "id": hashlib.sha1(f"{tool_id}{author}{datetime.now().isoformat()}".encode()).hexdigest()[:8],
        "author": author,
        "content": content,
        "rating": max(1, min(5, rating)),
        "timestamp": datetime.now().isoformat(),
        "likes": 0
    }
    
    comments[tool_id].append(comment)
    save_comments(comments)

def delete_comment(tool_id: str, comment_id: str) -> None:
    """Supprime un commentaire spécifique"""
    comments = load_comments()
    if tool_id in comments:
        comments[tool_id] = [c for c in comments[tool_id] if c.get("id") != comment_id]
        save_comments(comments)

def get_comments(tool_id: str) -> List[Dict[str, Any]]:
    comments = load_comments()
    return comments.get(tool_id, [])

# === Gestion des liens externes ===
def add_external_link(tool_id: str, title: str, url: str, link_type: str, description: str = "") -> None:
    links = load_links()
    if tool_id not in links:
        links[tool_id] = []
    
    link = {
        "id": hashlib.sha1(f"{tool_id}{title}{datetime.now().isoformat()}".encode()).hexdigest()[:8],
        "title": title,
        "url": url,
        "type": link_type,  # "youtube", "blog", "tutorial", "other"
        "description": description,
        "added_at": datetime.now().isoformat(),
        "rating": 0
    }
    
    links[tool_id].append(link)
    save_links(links)

def get_external_links(tool_id: str) -> List[Dict[str, Any]]:
    links = load_links()
    return links.get(tool_id, [])

def delete_external_link(tool_id: str, link_id: str) -> None:
    """Supprime un lien externe spécifique"""
    links = load_links()
    if tool_id in links:
        links[tool_id] = [l for l in links[tool_id] if l.get("id") != link_id]
        save_links(links)

# === Fonctions d'export/import unifiées ===
def export_all_data() -> Dict[str, Any]:
    """Exporte toutes les données dans un seul fichier JSON"""
    db = load_db()
    comments = load_comments()
    links = load_links()
    
    export_data = {
        "version": "1.0",
        "export_date": datetime.now().isoformat(),
        "tools": db.get("tools", []),
        "comments": comments,
        "external_links": links,
        "metadata": {
            "total_tools": len(db.get("tools", [])),
            "total_comments": sum(len(c) for c in comments.values()),
            "total_links": sum(len(l) for l in links.values())
        }
    }
    
    return export_data

def import_all_data(data: Dict[str, Any]) -> Dict[str, int]:
    """Importe toutes les données depuis un fichier JSON unifié"""
    results = {
        "tools_imported": 0,
        "comments_imported": 0,
        "links_imported": 0,
        "errors": []
    }
    
    try:
        # Vérifier la version
        version = data.get("version", "1.0")
        if version != "1.0":
            results["errors"].append(f"Version non supportée: {version}")
        
        # Importer les outils
        if "tools" in data and isinstance(data["tools"], list):
            db = load_db()
            existing_tools = {t.get("id") for t in db.get("tools", [])}
            
            for tool in data["tools"]:
                if isinstance(tool, dict) and (tool.get("name") or tool.get("link")):
                    # Normaliser l'outil
                    normalized = {
                        "name": tool.get("name", "").strip(),
                        "link": tool.get("link", "").strip(),
                        "description": tool.get("description", "").strip(),
                        "category": tool.get("category", "").strip(),
                        "keywords": tool.get("keywords", []) if isinstance(tool.get("keywords"), list) else [],
                        "price_euros_1_to_5": int(tool.get("price_euros_1_to_5", 3)),
                        "added_at": tool.get("added_at") or datetime.utcnow().isoformat() + "Z"
                    }
                    normalized["id"] = tool_id(normalized)
                    
                    # Vérifier si pas déjà présent
                    if normalized["id"] not in existing_tools:
                        db["tools"].append(normalized)
                        results["tools_imported"] += 1
                        existing_tools.add(normalized["id"])
            
            save_db(db)
        
        # Importer les commentaires
        if "comments" in data and isinstance(data["comments"], dict):
            comments = load_comments()
            for current_tool_id, tool_comments in data["comments"].items():
                if isinstance(tool_comments, list):
                    if current_tool_id not in comments:
                        comments[current_tool_id] = []
                    
                    for comment in tool_comments:
                        if isinstance(comment, dict) and comment.get("author") and comment.get("content"):
                            # Vérifier si le commentaire existe déjà
                            existing_comment_ids = {c.get("id") for c in comments[current_tool_id]}
                            if comment.get("id") not in existing_comment_ids:
                                comments[current_tool_id].append(comment)
                                results["comments_imported"] += 1
            
            save_comments(comments)
        
        # Importer les liens externes
        if "external_links" in data and isinstance(data["external_links"], dict):
            links = load_links()
            for current_tool_id, tool_links in data["external_links"].items():
                if isinstance(tool_links, list):
                    if current_tool_id not in links:
                        links[current_tool_id] = []
                    
                    for link in tool_links:
                        if isinstance(link, dict) and link.get("title") and link.get("url"):
                            # Vérifier si le lien existe déjà
                            existing_link_ids = {l.get("id") for l in links[current_tool_id]}
                            if link.get("id") not in existing_link_ids:
                                links[current_tool_id].append(link)
                                results["links_imported"] += 1
            
            save_links(links)
        
        # Importer les métadonnées
        if "metadata" in data:
            st.info(f"📊 Métadonnées de l'export: {data['metadata']}")
        
    except Exception as e:
        results["errors"].append(f"Erreur lors de l'import: {str(e)}")
    
    return results

def get_export_filename() -> str:
    """Génère un nom de fichier d'export avec la date"""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"toolsorter_export_{date_str}.json"

# === Fonctions de synchronisation ===
def sync_with_external_json(file_path: str, mode: str = "import") -> Dict[str, Any]:
    """
    Synchronise avec un fichier JSON externe
    mode: "import" pour lire, "export" pour écrire
    """
    try:
        if mode == "export":
            # Exporter toutes les données vers le fichier externe
            export_data = export_all_data()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"Données exportées vers {file_path}"}
        
        elif mode == "import":
            # Importer depuis le fichier externe
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            results = import_all_data(data)
            return {"success": True, "message": f"Import réussi: {results}"}
            
    except Exception as e:
        return {"success": False, "message": f"Erreur: {str(e)}"}

def get_sync_filename() -> str:
    """Génère un nom de fichier pour la synchronisation"""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"juktool_sync_{date_str}.json"

# === Synchronisation JSON ↔ GitHub ===
def github_sync_json(mode: str = "push") -> Dict[str, Any]:
    """Synchronise le fichier JSON avec GitHub (pull/push)"""
    try:
        # Vérifier si on est dans un repo Git
        result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode != 0:
            return {"success": False, "message": "Pas de repository Git configuré"}
        
        if mode == "push":
            # Exporter toutes les données vers un fichier JSON
            export_data = export_all_data()
            json_filename = "juktool_database.json"
            
            # Sauvegarder le JSON dans le repo
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            # Ajouter le fichier JSON au Git
            subprocess.run(["git", "add", json_filename], cwd=os.getcwd())
            
            # Commit avec timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = f"Sync JSON: {timestamp} - {export_data['metadata']['total_tools']} outils"
            
            result = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True, cwd=os.getcwd())
            if result.returncode != 0:
                if "nothing to commit" in result.stdout.lower():
                    return {"success": True, "message": "Aucun changement à synchroniser"}
                else:
                    return {"success": False, "message": f"Erreur commit: {result.stderr}"}
            
            # Push vers GitHub
            result = subprocess.run(["git", "push"], capture_output=True, text=True, cwd=os.getcwd())
            if result.returncode == 0:
                return {"success": True, "message": f"JSON synchronisé vers GitHub: {commit_msg}"}
            else:
                return {"success": False, "message": f"Erreur push: {result.stderr}"}
        
        elif mode == "pull":
            # Pull depuis GitHub
            result = subprocess.run(["git", "pull"], capture_output=True, text=True, cwd=os.getcwd())
            if result.returncode == 0:
                # Vérifier si le fichier JSON existe
                json_filename = "juktool_database.json"
                if os.path.exists(json_filename):
                    # Importer les données depuis le JSON
                    with open(json_filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Importer les données
                    results = import_all_data(data)
                    return {"success": True, "message": f"Données récupérées depuis GitHub: {results}"}
                else:
                    return {"success": True, "message": "Aucun fichier JSON trouvé sur GitHub"}
            else:
                return {"success": False, "message": f"Erreur pull: {result.stderr}"}
                
    except Exception as e:
        return {"success": False, "message": f"Erreur synchronisation: {str(e)}"}

def git_sync_to_github() -> Dict[str, Any]:
    """Alias pour la synchronisation push"""
    return github_sync_json("push")

def git_pull_from_github() -> Dict[str, Any]:
    """Alias pour la synchronisation pull"""
    return github_sync_json("pull")

def auto_sync_worker():
    """Worker pour la synchronisation automatique toutes les 5 minutes"""
    while True:
        try:
            time.sleep(300)  # 5 minutes
            if st.session_state.get("auto_sync_enabled", False):
                # Synchronisation automatique : push des données vers GitHub
                result = github_sync_json("push")
                if result["success"]:
                    st.session_state["last_auto_sync"] = datetime.now().isoformat()
                    st.session_state["auto_sync_status"] = "success"
                    st.session_state["last_sync_message"] = result["message"]
                else:
                    st.session_state["auto_sync_status"] = "error"
                    st.session_state["last_sync_error"] = result["message"]
        except Exception as e:
            st.session_state["auto_sync_status"] = "error"
            st.session_state["auto_sync_error"] = str(e)

def start_auto_sync():
    """Démarre la synchronisation automatique en arrière-plan"""
    if not st.session_state.get("auto_sync_started", False):
        st.session_state["auto_sync_started"] = True
        sync_thread = threading.Thread(target=auto_sync_worker, daemon=True)
        sync_thread.start()

# === Interface principale ===
# Vérifier si on est sur une page d'outil spécifique
tool_id_param = st.query_params.get("tool_id", None)

if tool_id_param:
    # === Page détaillée de l'outil ===
    db = load_db()
    tool = next((t for t in db.get("tools", []) if t.get("id") == tool_id_param), None)
    
    if tool:
        st.title(f"🔍 {tool.get('name', 'Outil')}")
        
        # Bouton retour
        if st.button("← Retour à la liste"):
            st.query_params.clear()
            st.rerun()
        
        # Informations principales
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"### 📝 Description")
            st.write(tool.get('description', 'Aucune description disponible'))
            
            if tool.get('keywords'):
                st.markdown(f"### 🏷️ Mots-clés")
                st.write(", ".join(tool['keywords']))
        
        with col2:
            st.markdown(f"### ℹ️ Informations")
            st.write(f"**Catégorie:** {tool.get('category', '–')}")
            st.write(f"**Prix:** {euros(tool.get('price_euros_1_to_5', 3))}")
            if tool.get('link'):
                st.write(f"**🔗 Lien:** [{tool['link']}]({tool['link']})")
            if tool.get('ai_enriched'):
                st.write("🤖 *Enrichi par IA*")
        
        st.divider()
        
        # Onglets pour commentaires et liens
        tab_comments, tab_links = st.tabs(["💬 Commentaires", "🔗 Liens externes"])
        
        # === Onglet Commentaires ===
        with tab_comments:
            st.subheader("💬 Commentaires et avis")
            
            # Formulaire d'ajout de commentaire
            with st.expander("✍️ Ajouter un commentaire", expanded=False):
                with st.form("add_comment"):
                    col1, col2 = st.columns(2)
                    with col1:
                        author = st.text_input("Votre nom", placeholder="Votre nom ou pseudo")
                    with col2:
                        rating = st.slider("Note (1-5)", 1, 5, 3)
                    
                    content = st.text_area("Votre commentaire", placeholder="Partagez votre expérience avec cet outil...")
                    
                    if st.form_submit_button("💬 Publier"):
                        if author and content:
                            add_comment(tool_id_param, author, content, rating)
                            st.success("Commentaire ajouté !")
                            st.rerun()
                        else:
                            st.error("Veuillez remplir tous les champs")
            
            # Affichage des commentaires
            comments = get_comments(tool_id_param)
            if comments:
                st.write(f"**{len(comments)} commentaire(s)**")
                for comment in sorted(comments, key=lambda x: x['timestamp'], reverse=True):
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{comment['author']}** - {comment['timestamp'][:10]}")
                            st.write(comment['content'])
                        with col2:
                            st.write(f"⭐ {'⭐' * comment['rating']}")
                            col_like, col_del = st.columns(2)
                            with col_like:
                                if st.button("👍", key=f"like_{comment['id']}"):
                                    comment['likes'] += 1
                                    save_comments(load_comments())
                                    st.rerun()
                                st.write(f"Likes: {comment['likes']}")
                            with col_del:
                                if st.button("🗑️", key=f"del_comment_{comment['id']}", help="Supprimer ce commentaire"):
                                    delete_comment(tool_id_param, comment['id'])
                                    st.success("Commentaire supprimé !")
                                    st.rerun()
            else:
                st.info("Aucun commentaire pour le moment. Soyez le premier !")
        
        # === Onglet Liens externes ===
        with tab_links:
            st.subheader("🔗 Liens externes")
            
            # Formulaire d'ajout de lien
            with st.expander("➕ Ajouter un lien", expanded=False):
                with st.form("add_link"):
                    col1, col2 = st.columns(2)
                    with col1:
                        title = st.text_input("Titre du lien", placeholder="ex: Tutoriel YouTube")
                        url = st.text_input("URL", placeholder="https://...")
                    with col2:
                        link_type = st.selectbox("Type", ["youtube", "blog", "tutorial", "other"])
                        rating = st.slider("Note (1-5)", 1, 5, 3)
                    
                    description = st.text_area("Description", placeholder="Description du lien...")
                    
                    if st.form_submit_button("🔗 Ajouter"):
                        if title and url:
                            add_external_link(tool_id_param, title, url, link_type, description)
                            st.success("Lien ajouté !")
                            st.rerun()
                        else:
                            st.error("Veuillez remplir le titre et l'URL")
            
            # Affichage des liens
            links = get_external_links(tool_id_param)
            if links:
                # Filtrer par type
                link_types = ["youtube", "blog", "tutorial", "other"]
                selected_type = st.selectbox("Filtrer par type", ["Tous"] + link_types)
                
                filtered_links = links
                if selected_type != "Tous":
                    filtered_links = [l for l in links if l['type'] == selected_type]
                
                st.write(f"**{len(filtered_links)} lien(s) trouvé(s)**")
                
                for link in filtered_links:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            # Icône selon le type
                            icon = {"youtube": "📺", "blog": "📝", "tutorial": "📚", "other": "🔗"}.get(link['type'], "🔗")
                            st.write(f"{icon} **{link['title']}**")
                            if link['description']:
                                st.write(link['description'])
                            st.write(f"[Ouvrir le lien]({link['url']})")
                        with col2:
                            st.write(f"⭐ {'⭐' * link['rating']}")
                            st.write(f"Type: {link['type']}")
                            st.write(f"Ajouté: {link['added_at'][:10]}")
                            if st.button("🗑️", key=f"del_link_{link['id']}", help="Supprimer ce lien"):
                                delete_external_link(tool_id_param, link['id'])
                                st.success("Lien supprimé !")
                                st.rerun()
            else:
                st.info("Aucun lien externe pour le moment. Ajoutez-en un !")
    
    else:
        st.error("Outil non trouvé")
        if st.button("← Retour à la liste"):
            st.query_params.clear()
            st.rerun()

else:
    # === Interface principale normale ===
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ajouter", "🔎 Recherche", "📦 Base", "⚙️ Options"])

    # --- Onglet Options ---
    with tab4:
        st.subheader("Configuration OpenAI")
        cfg = load_config()
        
        api_key = st.text_input("Clé API OpenAI", value=cfg.get("openai_api_key", ""), type="password")
        model = st.text_input("Modèle", value=cfg.get("openai_model", "gpt-4o-mini"))
        
        if st.button("💾 Sauvegarder"):
            cfg["openai_api_key"] = api_key.strip()
            cfg["openai_model"] = model.strip()
            save_config(cfg)
            st.success("Configuration sauvegardée !")
        
        st.divider()
        st.write("**Statut OpenAI:**", "✅ Actif" if have_openai() else "❌ Inactif")

    # --- Onglet Ajouter ---
    with tab1:
        st.subheader("Ajouter un outil")
        
        with st.form("add_tool"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nom*", placeholder="Ex: ChatGPT")
                link = st.text_input("Lien*", placeholder="https://...")
                description = st.text_area("Description", placeholder="Description courte")
            with col2:
                category = st.text_input("Catégorie", placeholder="ex: chatbot")
                keywords = st.text_input("Mots-clés (séparés par ;)", placeholder="IA; chat; texte")
                price = st.slider("Prix (1-5)", 1, 5, 3)
                use_ai = st.checkbox("Enrichir avec l'IA")
            
            submitted = st.form_submit_button("Ajouter")
            
            if submitted and name and link:
                db = load_db()
                
                tool = {
                    "name": name.strip(),
                    "link": link.strip(),
                    "description": description.strip(),
                    "category": category.strip(),
                    "keywords": normalize_kw(keywords),
                    "price_euros_1_to_5": price,
                    "added_at": datetime.utcnow().isoformat() + "Z"
                }
                
                if use_ai:
                    tool = ai_enrich(tool)
                
                tool["id"] = tool_id(tool)
                
                # Vérifier si l'outil existe déjà
                existing_ids = [t.get("id") for t in db.get("tools", [])]
                if tool["id"] in existing_ids:
                    st.warning("Cet outil existe déjà !")
                else:
                    db["tools"].append(tool)
                    save_db(db)
                    st.success(f"✅ {tool['name']} ajouté !")
                    st.json(tool)

    # --- Onglet Recherche ---
    with tab2:
        st.subheader("Rechercher dans la base")
        
        query = st.text_input("Recherche", placeholder="ex: chatbot IA")
        
        # Option pour utiliser GPT
        use_gpt = st.checkbox("🤖 Utiliser GPT pour la recherche intelligente", value=False)
        
        if query:
            db = load_db()
            tools = db.get("tools", [])
            
            if tools:
                # ÉTAPE 1: Recherche par mots-clés exacts
                query_lower = query.lower()
                exact_matches = []
                
                for t in tools:
                    # Vérifier dans le nom
                    if query_lower in t.get('name', '').lower():
                        exact_matches.append(t)
                        continue
                    
                    # Vérifier dans les mots-clés
                    if any(query_lower in kw.lower() for kw in t.get('keywords', [])):
                        exact_matches.append(t)
                        continue
                    
                    # Vérifier dans la catégorie
                    if query_lower in t.get('category', '').lower():
                        exact_matches.append(t)
                        continue
                
                # Si on a des résultats exacts, les afficher
                if exact_matches:
                    st.write(f"**🎯 {len(exact_matches)} résultats exacts trouvés**")
                    for t in exact_matches:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"### {t.get('name', 'Sans nom')}")
                                st.write(f"**Catégorie:** {t.get('category', '–')} | **Prix:** {euros(t.get('price_euros_1_to_5', 3))}")
                                if t.get('description'):
                                    st.write(t['description'])
                                if t.get('link'):
                                    st.write(f"🔗 {t['link']}")
                                if t.get('keywords'):
                                    st.write(f"**Mots-clés:** {', '.join(t['keywords'])}")
                                if t.get('ai_enriched'):
                                    st.write("🤖 *Enrichi par IA*")
                            with col2:
                                if st.button("🔍 Voir détails", key=f"view_{t['id']}"):
                                    st.query_params["tool_id"] = t['id']
                                    st.rerun()
                
                # ÉTAPE 2: Recherche intelligente seulement si pas de résultats exacts
                if not exact_matches:
                    if use_gpt and have_openai():
                        st.info("🧠 GPT analyse votre requête et la base de données...")
                        
                        # Préparer les données pour GPT
                        tools_for_gpt = []
                        for t in tools:
                            tools_for_gpt.append({
                                "id": t.get("id"),
                                "name": t.get("name", ""),
                                "description": t.get("description", ""),
                                "category": t.get("category", ""),
                                "keywords": t.get("keywords", []),
                                "link": t.get("link", "")
                            })
                        
                        try:
                            # Appel à GPT
                            prompt = f"""Tu es un expert en outils IA. L'utilisateur cherche: "{query}"

Voici la base de données d'outils disponibles:
{json.dumps(tools_for_gpt, ensure_ascii=False, indent=2)}

Trouve les 3-5 outils les plus pertinents pour cette requête. Réponds en JSON avec:
{{
    "analysis": "Analyse courte de la requête",
    "recommendations": [
        {{
            "id": "id_de_l_outil",
            "reason": "Pourquoi cet outil est recommandé"
        }}
    ]
}}"""

                            client = get_openai_client()
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                temperature=0.3,
                                messages=[{"role": "user", "content": prompt}],
                                response_format={"type": "json_object"}
                            )
                            
                            gpt_result = json.loads(response.choices[0].message.content)
                            
                            # Afficher l'analyse GPT
                            st.markdown("### 🤖 Analyse GPT")
                            st.write(gpt_result.get("analysis", ""))
                            
                            # Afficher les recommandations
                            st.markdown("### 🎯 Outils recommandés par GPT")
                            for rec in gpt_result.get("recommendations", []):
                                tool_id = rec.get("id")
                                tool = next((t for t in tools if t.get("id") == tool_id), None)
                                
                                if tool:
                                    with st.container(border=True):
                                        col1, col2 = st.columns([3, 1])
                                        with col1:
                                            st.markdown(f"### {tool.get('name', 'Sans nom')}")
                                            st.write(f"**Catégorie:** {tool.get('category', '–')} | **Prix:** {euros(tool.get('price_euros_1_to_5', 3))}")
                                            st.write(f"**💡 Raison:** {rec.get('reason', '')}")
                                            if tool.get('description'):
                                                st.write(tool['description'])
                                            if tool.get('link'):
                                                st.write(f"🔗 {tool['link']}")
                                            if tool.get('keywords'):
                                                st.write(f"**Mots-clés:** {', '.join(tool['keywords'])}")
                                            if tool.get('ai_enriched'):
                                                st.write("🤖 *Enrichi par IA*")
                                        with col2:
                                            if st.button("🔍 Voir détails", key=f"gpt_view_{tool['id']}"):
                                                st.query_params["tool_id"] = tool['id']
                                                st.rerun()
                        
                        except Exception as e:
                            st.error(f"Erreur GPT: {str(e)}")
                            st.info("Retour à la recherche classique...")
                            use_gpt = False
                    
                    # Si pas de GPT ou erreur, utiliser la recherche classique
                    if not use_gpt or not have_openai():
                        st.info("🔍 Aucun résultat exact trouvé. Recherche intelligente en cours...")
                        
                        def score_tool(t):
                            text = f"{t.get('name', '')} {t.get('description', '')} {' '.join(t.get('keywords', []))} {t.get('category', '')}"
                            return fuzz.token_set_ratio(query_lower, text.lower())
                        
                        # Recherche par similarité
                        smart_results = sorted(tools, key=score_tool, reverse=True)[:5]
                        
                        st.write(f"**🧠 {len(smart_results)} suggestions intelligentes**")
                        for t in smart_results:
                            with st.container(border=True):
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.markdown(f"### {t.get('name', 'Sans nom')}")
                                    st.write(f"**Catégorie:** {t.get('category', '–')} | **Prix:** {euros(t.get('price_euros_1_to_5', 3))}")
                                    if t.get('description'):
                                        st.write(t['description'])
                                    if t.get('link'):
                                        st.write(f"🔗 {t['link']}")
                                    if t.get('keywords'):
                                        st.write(f"**Mots-clés:** {', '.join(t['keywords'])}")
                                    if tool.get('ai_enriched'):
                                        st.write("🤖 *Enrichi par IA*")
                                with col2:
                                    if st.button("🔍 Voir détails", key=f"smart_view_{t['id']}"):
                                        st.query_params["tool_id"] = t['id']
                                        st.rerun()
            else:
                st.info("Aucun outil dans la base. Ajoutez-en d'abord !")

    # --- Onglet Base ---
    with tab3:
        st.subheader("Gestion de la base")
        
        # Information sur le format d'export unifié
        with st.expander("ℹ️ Format d'export/import unifié", expanded=False):
            st.markdown("""
            **📦 Export unifié ToolSorter** - Un seul fichier JSON qui contient tout :
            
            - 🧰 **Outils** : Nom, description, catégorie, mots-clés, prix
            - 💬 **Commentaires** : Avis des utilisateurs avec notes et likes
            - 🔗 **Liens externes** : YouTube, blogs, tutoriels, autres ressources
            
            **🔄 Compatibilité** : 
            - ✅ Import automatique des anciens formats
            - ✅ Détection intelligente du type de fichier
            - ✅ Fusion sans doublons
            - ✅ Métadonnées et statistiques
            
            **📁 Nom du fichier** : `toolsorter_export_YYYYMMDD_HHMMSS.json`
            """)
        
        # === Synchronisation JSON ↔ GitHub ===
        st.subheader("🔄 Synchronisation JSON ↔ GitHub")
        st.info("💡 **Synchronisation automatique** : L'app envoie/récupère le fichier JSON depuis GitHub toutes les 5 minutes")
        
        # Initialiser la session state
        if "auto_sync_enabled" not in st.session_state:
            st.session_state["auto_sync_enabled"] = False
        if "last_auto_sync" not in st.session_state:
            st.session_state["last_auto_sync"] = None
        if "auto_sync_status" not in st.session_state:
            st.session_state["auto_sync_status"] = "idle"
        
        # Démarrer la synchronisation automatique
        start_auto_sync()
        
        col_gh1, col_gh2, col_gh3 = st.columns(3)
        
        with col_gh1:
            # Synchronisation manuelle vers GitHub
            if st.button("📤 Envoyer JSON vers GitHub", type="primary"):
                with st.spinner("Envoi du JSON en cours..."):
                    result = github_sync_json("push")
                    if result["success"]:
                        st.success(result["message"])
                        st.session_state["last_auto_sync"] = datetime.now().isoformat()
                        st.session_state["auto_sync_status"] = "success"
                        st.session_state["last_sync_message"] = result["message"]
                    else:
                        st.error(result["message"])
                        st.session_state["auto_sync_status"] = "error"
                        st.session_state["last_sync_error"] = result["message"]
        
        with col_gh2:
            # Récupération depuis GitHub
            if st.button("📥 Récupérer JSON depuis GitHub"):
                with st.spinner("Récupération du JSON en cours..."):
                    result = github_sync_json("pull")
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()  # Recharger les données
                    else:
                        st.error(result["message"])
        
        with col_gh3:
            # Activation/désactivation de la synchronisation automatique
            auto_sync_enabled = st.checkbox(
                "🔄 Sync auto (5 min)", 
                value=st.session_state.get("auto_sync_enabled", False),
                help="Synchronisation automatique toutes les 5 minutes"
            )
            st.session_state["auto_sync_enabled"] = auto_sync_enabled
        
        # Statut de la synchronisation JSON
        if st.session_state.get("last_auto_sync"):
            last_sync = datetime.fromisoformat(st.session_state["last_auto_sync"])
            time_diff = datetime.now() - last_sync
            
            if time_diff.total_seconds() < 300:  # Moins de 5 minutes
                st.success(f"✅ Dernière sync JSON: {time_diff.total_seconds():.0f}s")
                if st.session_state.get("last_sync_message"):
                    st.info(f"📝 {st.session_state['last_sync_message']}")
            else:
                st.warning(f"⚠️ Dernière sync JSON: {time_diff.total_seconds()//60}min")
        
        if st.session_state.get("auto_sync_status") == "error":
            st.error("❌ Erreur de synchronisation automatique")
            if st.session_state.get("last_sync_error"):
                st.error(f"🔍 Détail: {st.session_state['last_sync_error']}")
        
        st.divider()
        
        # === Synchronisation externe (fichier JSON) ===
        st.subheader("📁 Partage par fichier JSON")
        st.info("💡 **Partagez vos données** : Exportez vers un fichier JSON, puis partagez-le avec d'autres utilisateurs")
        
        col_sync1, col_sync2 = st.columns(2)
        
        with col_sync1:
            # Export pour synchronisation
            db = load_db()
            current_tools = db.get("tools", [])
            
            if current_tools:
                sync_filename = get_sync_filename()
                export_data = export_all_data()
                export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
                
                st.download_button(
                    "📤 Exporter pour partage",
                    data=export_json,
                    file_name=sync_filename,
                    mime="application/json",
                    help="Exporte toutes les données pour partage avec d'autres utilisateurs"
                )
                
                st.caption(f"📊 {len(current_tools)} outils, {sum(len(c) for c in load_comments().values())} commentaires")
            else:
                st.info("Base vide - rien à exporter")
        
        with col_sync2:
            # Import depuis fichier externe
            uploaded_sync = st.file_uploader(
                "📥 Importer depuis partage", 
                type=["json"],
                help="Importe les données partagées par d'autres utilisateurs"
            )
            
            if uploaded_sync is not None:
                try:
                    content = uploaded_sync.read()
                    data = json.loads(content.decode('utf-8'))
                    
                    # Utiliser la fonction d'import unifiée
                    results = import_all_data(data)
                    
                    if results["errors"]:
                        st.error(f"❌ Erreurs: {results['errors']}")
                    
                    if results["tools_imported"] > 0 or results["comments_imported"] > 0 or results["links_imported"] > 0:
                        st.success(f"✅ Synchronisation réussie ! "
                                 f"{results['tools_imported']} outils, "
                                 f"{results['comments_imported']} commentaires, "
                                 f"{results['links_imported']} liens")
                        st.rerun()
                    else:
                        st.info("ℹ️ Aucune nouvelle donnée à importer")
                        
                except Exception as e:
                    st.error(f"❌ Erreur d'import: {str(e)}")
        
        st.divider()
        
        db = load_db()
        tools = db.get("tools", [])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export unifié
            if tools:
                export_data = export_all_data()
                export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
                filename = get_export_filename()
                
                st.download_button(
                    "📥 Exporter TOUT (JSON unifié)",
                    data=export_json,
                    file_name=filename,
                    mime="application/json",
                    help="Exporte outils + commentaires + liens externes"
                )
                
                # Afficher les statistiques
                st.caption(f"📊 {export_data['metadata']['total_tools']} outils, "
                          f"{export_data['metadata']['total_comments']} commentaires, "
                          f"{export_data['metadata']['total_links']} liens")
            else:
                st.info("Base vide")
        
        with col2:
            # Import unifié
            uploaded = st.file_uploader("Importer JSON unifié", type=["json"], 
                                      help="Importe outils + commentaires + liens externes")
            if uploaded is not None:
                try:
                    content = uploaded.read()
                    data = json.loads(content.decode('utf-8'))
                    
                    # Utiliser la fonction d'import unifiée
                    results = import_all_data(data)
                    
                    if results["errors"]:
                        st.error(f"Erreurs lors de l'import: {results['errors']}")
                    
                    if results["tools_imported"] > 0 or results["comments_imported"] > 0 or results["links_imported"] > 0:
                        st.success(f"✅ Import réussi ! "
                                 f"{results['tools_imported']} outils, "
                                 f"{results['comments_imported']} commentaires, "
                                 f"{results['links_imported']} liens")
                        st.rerun()
                    else:
                        st.info("Aucune nouvelle donnée à importer")
                        
                except Exception as e:
                    st.error(f"Erreur d'import: {str(e)}")
        
        with col3:
            # Nettoyage
            if tools:
                if st.button("🧹 Nettoyer"):
                    cleaned = dedupe_tools(tools)
                    save_db({"tools": cleaned})
                    st.success(f"Base nettoyée : {len(cleaned)} outils uniques")
                    st.rerun()
        
        # Affichage de la base
        if tools:
            st.divider()
            st.write(f"**Base actuelle : {len(tools)} outils**")
            
            # Recherche rapide
            search = st.text_input("🔍 Filtrer", placeholder="Filtrer par nom, catégorie...")
            if search:
                filtered = [t for t in tools if search.lower() in 
                           f"{t.get('name', '')} {t.get('category', '')} {' '.join(t.get('keywords', []))}".lower()]
                tools_to_show = filtered
            else:
                tools_to_show = tools[:50]  # Limiter l'affichage
            
            for tool in tools_to_show:
                with st.container(border=True):
                    colA, colB, colC, colD = st.columns([3, 2, 1, 1])
                    with colA:
                        st.markdown(f"**{tool.get('name', 'Sans nom')}**")
                        if tool.get('link'):
                            st.write(f"🔗 {tool['link']}")
                    with colB:
                        st.write(f"Catégorie: {tool.get('category', '–')}")
                        st.write(f"Prix: {euros(tool.get('price_euros_1_to_5', 3))}")
                    with colC:
                        if st.button("🔍 Détails", key=f"details_{tool['id']}"):
                            st.query_params["tool_id"] = tool['id']
                            st.rerun()
                    with colD:
                        if st.button("🗑️", key=f"del_{tool['id']}"):
                            tools.remove(tool)
                            save_db({"tools": tools})
                            st.success("Supprimé !")
                            st.rerun()
                    
                    if tool.get('description'):
                        st.write(tool['description'])
                    if tool.get('keywords'):
                        st.write(f"**Mots-clés:** {', '.join(tool['keywords'])}")
        else:
            st.info("Aucun outil dans la base. Commencez par en ajouter !")

# 🧰 ToolSorter - Gestionnaire d'outils IA

## 📱 **Comment utiliser l'application :**

1. **Lancer l'app** : `streamlit run JukTool.py`
2. **Ajouter des outils** dans l'onglet "Ajouter"
3. **Rechercher** dans l'onglet "Recherche"
4. **Gérer la base** dans l'onglet "Base"

## 🔄 **Synchronisation GitHub automatique :**

### **Fonctionnalités :**
- ✅ **Synchronisation automatique** à chaque sauvegarde
- ✅ **Synchronisation toutes les 5 minutes** (optionnelle)
- ✅ **Push automatique** vers votre repository GitHub
- ✅ **Pull automatique** depuis GitHub

### **Configuration GitHub :**
1. **Créez un repository GitHub** pour vos données
2. **Clonez-le** dans le dossier de l'application
3. **Activez la synchronisation** dans l'onglet "Base"
4. **Cochez "🔄 Sync auto (5 min)"** pour l'automatisation

### **Commandes Git de base :**
```bash
# Initialiser Git (si pas déjà fait)
git init

# Ajouter votre repository GitHub
git remote add origin https://github.com/votre-username/votre-repo.git

# Premier commit
git add .
git commit -m "Initial commit"
git push -u origin main
```

## 🔐 **Configuration OpenAI (optionnel) :**
1. Créez un fichier `.env` dans le dossier de l'app
2. Ajoutez : `OPENAI_API_KEY=votre_clé_ici`
3. Redémarrez l'application

## 📁 **Structure des données :**
- **Outils** : Nom, description, catégorie, mots-clés, prix
- **Commentaires** : Avis des utilisateurs avec notes
- **Liens externes** : YouTube, blogs, tutoriels

## 🚀 **Fonctionnalités :**
- ✅ Ajout d'outils avec enrichissement IA
- ✅ Recherche intelligente
- ✅ Système de commentaires et likes
- ✅ Gestion des liens externes
- ✅ Export/import unifié
- ✅ **Synchronisation GitHub automatique**
- ✅ **Synchronisation toutes les 5 minutes**

## 🔧 **Dépannage :**
- **Erreur Git** : Vérifiez que Git est installé et configuré
- **Repository non trouvé** : Vérifiez l'URL du remote GitHub
- **Conflits** : Utilisez "📥 Récupérer depuis GitHub" pour résoudre

---
*Synchronisez automatiquement vos outils IA avec GitHub ! 🎯*

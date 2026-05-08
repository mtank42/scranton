# Scranton — Backlog
> Features identifiées avant le go, hors roadmap POC initiale.
> Chaque entrée inclut : description, scope suggéré, et questions à résoudre pour le data model.
> Last updated: May 2026 — session data model

---

## Tell Dwight — Capture vocale asynchrone ("dans le camion")

**Catégorie** : Tell Dwight / Capture
**Priorité** : V2
**Origine** : session use cases menuiserie — le moment de vie non capturé par définition

### Description

Mode de capture vocale pour Tell Dwight, pensé pour les moments hors bureau : chantier, trajet, machine à café. Le manager dicte une note courte comme un vocal WhatsApp. Dwight ne l'interrompt pas. Quand le manager repasse au bureau, Dwight présente le batch de la journée : "Tu m'as laissé 3 notes aujourd'hui. Je te propose de les ranger là, ici et encore là." Le manager valide ou ajuste le routage proposé.

### UX flow

1. Mobile : le manager enregistre une note vocale (interface simple, un bouton)
2. La note est transcrite et mise en file d'attente (statut `pending`)
3. Dwight traite en arrière-plan : transcription → segmentation → proposition de routage
4. Au retour au bureau : notification "X notes en attente de validation"
5. Le manager valide ou ajuste le routage segment par segment
6. Les segments validés entrent dans le pipeline normal (ChromaDB + vues)

### Impact sur le data model

Aucun changement de schéma. Le champ `source_type` sur `entries` accueille simplement `voice_note`. Le pipeline Dwight est identique.

### Questions à résoudre avant de coder

**1. Moteur de transcription**
Whisper est d'OpenAI — hors stack. Options souveraines :
- Whisper open source en local (modèle `whisper.cpp` sur Mac Mini M4 — viable)
- Web Speech API native du navigateur (pas de serveur, mais qualité variable et dépendance au navigateur)
- Mistral speech-to-text si disponible au moment du dev V2

**2. Interface mobile**
PWA (Progressive Web App) dans le même frontend HTML/CSS/JS, ou application native ? La PWA est cohérente avec le stack POC et évite un second projet.

**3. Offline-first**
Si le manager est sans réseau sur le chantier, la note doit pouvoir être enregistrée localement et synchronisée au retour. À définir avec l'architecture de déploiement V2.

### Notes complémentaires

- Ce mode résout le cas d'usage le plus fréquent et le moins capturé : la décision prise hors bureau
- Le modèle batch ("je te propose X rangements") est intentionnel — Dwight n'interrompt pas, il attend
- À distinguer de Whisper Jim (chat éphémère) : ici c'est de la capture pour Pam, pas de la conversation

---

## Transfer to Philly

**Catégorie** : Transitions / Handover
**Priorité** : V1 (cas 1) — V2 (cas 2 + interopérabilité)
**Naming** : final, dans l'univers Dunder Mifflin (Scranton → Philadelphia, même État)

### Description

Feature de gestion des transitions — quand un employé change d'équipe ou quand le manager est remplacé. Facilite la passation de connaissance sans perdre la mémoire collective ni exposer des données sensibles sans consentement.

### Cas 1 — Transfert d'un employé vers une autre équipe

1. Le manager demande à Michael une fiche complète sur l'employé concerné
2. Michael génère deux blocs distincts :
   - **Données froides** : faits objectifs (projets, compétences, tâches, présence, historique)
   - **Données chaudes** : observations subjectives du manager (notes 1:1, évaluations, signaux faibles), triées par ordre de sensibilité
3. Le manager sélectionne ce qu'il souhaite transmettre parmi les données chaudes (toutes les données froides sont a priori transmissibles)
4. Le document proposé est soumis à l'employé, qui peut proposer des modifications
5. Les deux parties valident le document final
6. Angela exporte et envoie au Scranton du nouveau manager

**Scope POC** : génération de la fiche + export PDF validé par les deux parties.

### Cas 2 — Succession du manager

1. Le manager sortant déclenche "Transfer to Philly" depuis Michael's Desk
2. Michael génère une fiche par membre de l'équipe (mode batch pour N membres)
3. Le manager fait le même travail qu'en cas 1 pour chaque fiche
4. Le manager peut supprimer ses données chaudes personnelles (observations, notes subjectives qui lui appartiennent en propre) avant transmission
5. Toby génère un rapport de synthèse d'équipe pour le successeur
6. Deux options de transmission :
   - Angela envoie l'ensemble des fiches au successeur
   - Transmission d'une instance Scranton "nettoyée" (données chaudes personnelles supprimées) incluant l'accès à Pam

**Scope V1** : batch de fiches + export structuré.
**Scope V2** : transmission d'instance + interopérabilité entre Scranton.

---

### Alignement RGPD

La boucle de validation employé (étape 4 du cas 1) n'est pas optionnelle — elle est alignée avec le droit d'accès aux données personnelles (RGPD/CNIL). C'est une contrainte légale transformée en feature produit.

---

### Questions pour le data model — à résoudre avant de coder

**1. Distinction froid / chaud native dans le schéma**
La séparation données froides / données chaudes doit être un attribut de chaque entrée dès la conception, pas un tag ajouté en retro-fit.
→ *Chaque note, observation ou événement doit porter un champ `data_type` (cold / warm) et un champ `sensitivity_level` (1–5 ?) dès le schéma initial.*

**2. Propriété des données chaudes**
Certaines données chaudes "appartiennent" au manager (ses observations personnelles). D'autres appartiennent à l'équipe (tendances mood, actions de 1:1).
→ *Faut-il un champ `owner` (manager_id vs team) sur chaque entrée sensible ? Comment modéliser le droit de suppression sélective ?*

**3. Export de Pam (ChromaDB)**
"Transmettre l'accès à Pam" en cas 2 = exporter la base vectorielle.
→ *Définir un format d'export ChromaDB dès l'architecture initiale. Quelles collections sont transmissibles ? Avec quel niveau de filtrage ?*

**4. Consentement employé — traçabilité**
La validation à deux parties doit être auditée (qui a validé quoi, quand).
→ *Table `handover_validations` avec statuts (proposed / employee_reviewed / both_validated / sent) et timestamps. Signatures ou simple boolean ?*

**5. Interopérabilité entre instances (V2)**
"Envoyer au Scranton du nouveau manager" suppose un protocole d'échange entre instances.
→ *Pour le POC : export ZIP ou PDF suffit. Pour V2 : définir un format d'import/export structuré (JSON ?) avant de coder l'export POC, pour ne pas avoir à tout refaire.*

**6. Suppression sélective des données chaudes du manager sortant**
Le manager doit pouvoir purger ses observations personnelles sans toucher aux données d'équipe.
→ *La suppression doit être traçable (soft delete avec `deleted_by_manager_at`) plutôt qu'une suppression physique, pour des raisons d'audit.*

---

### Notes complémentaires

- Pour une équipe de 10, le cas 2 doit être en **batch** — une interface séquentielle fiche par fiche serait inutilisable.
- Le naming interne des états du workflow (proposed / reviewed / validated / sent) doit être défini une fois et réutilisé partout.
- Feature à mentionner dans le README comme différenciateur : "knowledge continuity across team transitions."

---

## Pistes écosystème — à explorer avant V2

### LaSuite numérique (DINUM)
Open source, souverain, utilisable par le privé. APIs disponibles sur `integration.lasuite.numerique.gouv.fr`.
- **Grist Core** (self-hostable) : tableur/base de données collaboratif. Pertinent pour Send Angela (exports structurés).
- **Docs** : éditeur collaboratif. Pourrait alimenter l'affichage des Smart Summaries.
- Argument de positionnement pour le README : "même philosophie que les outils numériques de l'État français."

### Albert API
LLM souverain français (DINUM). Alternative ou complément à Mistral si le projet évolue vers le secteur public ou un positionnement EU renforcé.

### GitHub MCP
À installer avant le go. Permet de gérer issues, PRs, et repo depuis Claude Code sans changer de contexte. Le repo doit être propre dès le premier commit.

---

## Recommandations extensions VS Code

- `Python` + `Pylance` — indispensable
- `REST Client` — tester les routes FastAPI sans quitter l'éditeur
- `SQLite Viewer` — inspecter la base SQLite visuellement
- `GitLens` — historique git ligne par ligne
- `Thunder Client` — API testing léger

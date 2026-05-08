# Scranton — Backlog
> Features identifiées avant le go, hors roadmap POC initiale.
> Chaque entrée inclut : description, scope suggéré, et questions à résoudre pour le data model.
> Last updated: May 2026 — session data model

---

## Profil humain + Maire de Scranton

**Catégorie** : Team member profile / Culture / Lien social
**Priorité** : V1 (profil humain) — V1 (maire de Scranton, événement anniversaire)
**Origine** : session data model — observation sur les clans Helio (fondateurs vs nouveaux)

### Problème

Scranton capte la couche professionnelle. Mais le lien entre équipiers se crée par la connaissance mutuelle des personnes, pas des rôles. Dans une équipe qui scale vite (comme Helio), les "nouveaux" restent des inconnus. Scranton peut contribuer à briser ça.

### Profil humain — "ce qu'ils aiment"

Chaque team member a un profil personnel en plus de son profil professionnel. Données déclarées par le manager (observées en 1:1, en conversation) ou saisies par le membre lui-même en V2.

Exemples : né le 11 février, fan de New Order, obsédé par la période Madchester, Moebius, les oursons en guimauve.

Ce n'est pas un formulaire RH. C'est ce que tu saurais d'un collègue après 3 mois si tu l'écoutais vraiment.

**Mécanisme** : Tell Dwight peut extraire ces informations depuis une note de 1:1. Si le manager écrit "Maxime m'a dit qu'il est né le 11 février et qu'il est fan de New Order", Dwight propose de l'ajouter au profil humain de Maxime.

### Maire de Scranton — l'anniversaire comme rituel

Le jour de l'anniversaire d'un membre de l'équipe, il devient **Maire de Scranton** pour 24h :
- L'interface Scranton adopte ses couleurs préférées (si renseignées) ou une palette générée depuis ses centres d'intérêt
- Un badge "Maire de Scranton" apparaît sur son profil toute la journée
- Pam envoie un rappel au manager **une semaine avant** : "L'anniversaire de Maxime est dans 7 jours. Tu veux préparer quelque chose avec l'équipe ?" — avec un rappel de ses centres d'intérêt pour inspirer
- That's What She Said se déclenche automatiquement le jour J

C'est un rituel annuel, prédictible, positif. Zéro bureaucratie. Pam gère.

### Impact sur le data model

**`birthday`** : champ date à ajouter sur `team_members`. Simple, non bloquant, à inclure dans le schéma initial avant de scaffolder les tables.

**`personal_profile`** : texte libre sur `team_members`, ou table séparée `team_member_profile` si on veut structurer par catégories (musique, culture, food, etc.). À décider en session.

**Sensibilité** : données personnelles au sens RGPD. Warm data, sensitivity_level élevé. Le membre doit pouvoir consulter et corriger son propre profil (V2). Le manager ne peut pas partager ce profil sans consentement.

### Questions à résoudre

1. **`personal_profile` : texte libre ou table structurée ?** Texte libre est plus naturel pour la saisie ("fan de New Order, obsédé par Madchester") mais moins queryable. Table structurée avec catégories permet à Pam de faire des corrélations ("deux membres de l'équipe aiment le jazz, tu le savais ?").

2. **Extraction automatique par Dwight** : quand Dwight repère une information personnelle dans une note, propose-t-il systématiquement de l'ajouter au profil humain, ou seulement si le manager le demande ?

3. **Visibilité entre équipiers** : en V2, les membres voient-ils le profil humain des autres ? C'est la dimension "lien social" — mais c'est aussi une question de consentement.

### Notes complémentaires

- Le "Maire de Scranton" est nommé dans l'univers The Office (Scranton, PA). À confirmer comme nom final.
- Ce mécanisme répond directement au cas Helio : les "nouveaux" ne resteraient pas des inconnus si Scranton rendait les personnes visibles en tant que personnes, pas seulement en tant que rôles.
- Potentiel fort pour le storytelling produit et le marketing — c'est la feature qui montre que Scranton n'est pas un outil RH.

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

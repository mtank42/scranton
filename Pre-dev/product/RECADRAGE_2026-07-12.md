# Recadrage produit — 2026-07-12 (session QA avec le owner)

> **STATUT : EXÉCUTÉ EN ENTIER le 2026-07-13** (étape 1 : `16f591d` ;
> étapes 2-3-6 : `c5f9a22` ; étapes 4-5 : `b0ae921`), puis validé par
> la première QA owner du produit recadré le 2026-07-14 (35/37, lot A
> de correctifs : `27dea70` — dont la règle « Pam cold-only, l'humain
> vit chez Toby et Michael's Desk », désormais invariant dans
> CLAUDE.md). Ce document reste la référence produit des 5 vues.

> **Ce document prime sur SCRANTON_CONTEXT §3 et sur l'UI construite.**
> Il capture, dans les mots du owner, le produit tel que les slides
> (`Pre-dev/pitch/scranton_slides_v6.html`) le décrivaient déjà et tel
> que le POC doit le devenir. Rédigé le dernier soir d'accès à Fable ;
> la prochaine session d'implémentation démarre ICI, sans réinterpréter.

## Le constat (première vraie passe QA du owner)

Le moteur est bon (porte de validation, verbatim, jamais de score,
coutures : tout tient). Le produit, lui, n'est pas reconnaissable :
l'app construite est un onglet par agent, alors que les slides — la
source de vérité UX — décrivent **un OS à deux vues par rôle** (slide
08 : manager view / team member view) où Dwight, Pam et Jim sont des
*actions omniprésentes* (+, ?, ~), pas des écrans. La chaîne
slides → specs distillées → code a perdu l'esprit en route.

Enseignement de maintenance : **les slides et le storytelling sont la
boussole UX**. Les specs distillées (CONTEXT §3, ROADMAP) sont des
inventaires, pas des maquettes. En cas de doute : slides d'abord.

## Les 5 vues du POC (liste fermée, owner 2026-07-12)

1. **Tell Dwight** (tous) — la capture. La box d'input DESCEND sous les
   propositions de Dwight à chaque note ("Anything else to tell
   Dwight?") et reste lisible.
2. **Pretzel Day** (équipiers) — le lieu PRIVÉ de chacun : son humeur
   (comme aujourd'hui), ET ce qu'il choisit de partager sur lui
   (anniversaire, goûts...). Mention très explicite : "partagé avec le
   manager, et lui seul, pour l'aider à ce que l'équipe se sente bien".
   Remplace le panneau de contrôle des paramètres tant qu'il n'existe
   pas. → Le manager ne saisit PLUS JAMAIS les données perso d'autrui ;
   la saisie par procuration disparaît.
3. **Ask Pam** (tous) — la mémoire interrogeable. Les Smart Summaries
   NE SONT PAS un écran : ce sont des **templates de réponse** que Pam
   sert quand la question s'y prête ("les infos sur Stone & Son" → le
   format Client). Le mot "file" disparaît partout (aucun sens). Pam
   agrège ; les ajouts/retraits dans un summary passent par Dwight,
   parce que c'est le manager qui décide. C'est PARTOUT, pas isolé.
4. **Michael's Desk** (manager) — la gestion des 1:1 et réunions :
   "l'ordre du jour du prochain 1:1 avec Ryan" ou "de la prochaine
   réunion d'équipe" → proposé ici au format Meeting. Porte à terme
   Transfer to Philly (nativement transition-proof, cf. slide 07).
5. **Meet Toby** (manager) — la santé d'équipe. Par équipier : les
   signaux QU'IL A VERBALISÉS (notes de check-in, segments warm datés,
   cités), pas seulement des pastilles à mille causes possibles. Toby
   AFFICHE aussi ce que chacun a déclaré via Pretzel Day (anniversaire,
   goûts) : pas de contradiction — le manager y a ACCÈS parce que
   c'est sciemment donné, il n'y TOUCHE jamais. Accès ≠ propriété.

## Ce qui saute

- **La vue Smart Summaries** (absorbée par Pam et Michael's Desk).
- **La vue Team** (le member-owned se déclare dans Pretzel Day, se
  consulte dans Toby ; le lien "Transfer to Philly" n'avait rien à y
  faire — la passation est V2/V3, rattachée à Michael's Desk).
- **La saisie par procuration** (humeur d'autrui, profil d'autrui) :
  chaque équipier remplit pour lui-même. Le POC assume d'être
  multi-rôle sur une même machine plutôt que mono-utilisateur déguisé.
- **Les tags cryptiques** : libellés humains, noms résolus, confidence
  visible — la clarté partout.

## Ce qui reste vrai (les invariants ne bougent pas)

Validation = seule porte vers la mémoire · SQLite source de vérité ·
verbatim RGPD du handover · jamais de score de personne · année
d'anniversaire effacée · coutures (LLM/ingestion/vector/characters) ·
le modèle de données 9 tables (il porte déjà tout ce recadrage :
`submitted_by_id`, data ownership split, view_types — c'est l'UI qui
était fausse, pas le schéma).

## Séquencement (owner, 2026-07-12)

- **POC recadré** : les 5 vues ci-dessus, produit "beaucoup plus
  simple". Esthétique : non prioritaire ("pur Claude", le owner s'y
  fait) — le jour venu, passe design avec SA direction artistique.
- **V2/V3** : une Pam vraiment à la hauteur (elle clarifie avant de
  répondre, elle rédige des brouillons — c'est slide 05 et ce n'est
  toujours pas implémenté), des TWSS beaucoup plus drôles et visuels,
  Whisper Jim, puis Send Angela et Transfer to Philly (passation au
  nouveau manager : c'est son SEUL but), design.

## Première session d'implémentation (ordre suggéré)

1. Réviser SCRANTON_CONTEXT §3 pour aligner la lettre sur ce document
   (les slides restent la référence UX).
2. La refonte de l'IA d'écran : 5 vues, rôles, Dwight/Pam en actions.
3. Pretzel Day côté équipier (humeur + partage volontaire de soi).
4. Pam sert les templates (suppression de l'écran Summaries), "file"
   banni du vocabulaire.
5. Toby : drill-down par équipier sur les signaux verbalisés + les
   infos déclarées.
6. Les tags lisibles (déjà acté avant recadrage).

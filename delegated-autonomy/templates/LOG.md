# Log

Mandate: autonomous until <YYYY-MM-DD HH:MM TZ>. Free: <...>. Reserved: <...>.
Stop rules: <...>; safe state: <...>. Conditions on approvals: "<operator's words>".
AI routing: build <provider/model>, review <provider/model>, fallback <...>, never <...>. (operator: "<words>")
Plan (approved <date>, "<operator's words>"): 1) ... 2) ... 3) ...

- <YYYY-MM-DD HH:MM TZ> <event>. <evidence: commit, log path, marker>. Next: <...>
- <HH:MM> Operator: "<words>" -> <what changes>. Memory updated: <name>.
- <HH:MM> **NOT done**: <step> (<reason>). Waiting for: <decision>.
- <HH:MM> **STOPPED** <item>: stop rule <rule> fired (<evidence>). Production left in <safe state>. Other items continue.
- <HH:MM> AI routing change: "<operator's words>" -> <new routing>, expires <time or never>.

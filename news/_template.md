{% macro reference(value) -%}
   {%- if value.startswith("PR") -%}
     [PR #{{ value[2:] }}](https://github.com/fedora-infra/sqlalchemy-helpers/issues/{{ value[2:] }})
   {%- elif value.startswith("C") -%}
     [{{ value[1:] }}](https://github.com/fedora-infra/sqlalchemy-helpers/commits/{{ value[1:] }})
   {%- else -%}
     [#{{ value }}](https://github.com/fedora-infra/sqlalchemy-helpers/issues/{{ value }})
   {%- endif -%}
{%- endmacro -%}

{{- top_line -}}

Released on {{ versiondata.date }}. This is a {major|feature|bugfix} release that adds [short summary].

{% for section, _ in sections.items() -%}
{%- if section -%}
## {{section}}
{%- endif -%}

{%- if sections[section] -%}
{%- for category, val in definitions.items() if category in sections[section] and category != "author" -%}
### {{ definitions[category]['name'] }}

{% if definitions[category]['showcontent'] -%}
{%- for text, values in sections[section][category].items() %}
- {{ text }}
{%- if values %}
{% if "\n  - " in text or '\n  * ' in text %}


  (
{%- else %}
 (
{%- endif -%}
{%- for issue in values %}
{{ reference(issue) }}{% if not loop.last %}, {% endif %}
{%- endfor %}
)
{% else %}

{% endif %}
{% endfor -%}
{%- else -%}
- {{ sections[section][category]['']|sort|join(', ') }}

{% endif -%}
{%- if sections[section][category]|length == 0 %}
No significant changes.

{% else -%}
{%- endif %}

{% endfor -%}
{% if sections[section]["author"] -%}
### {{definitions['author']["name"]}}

Many thanks to the contributors of bug reports, pull requests, and pull request
reviews for this release:

{% for text, values in sections[section]["author"].items() -%}
- {{ text }}
{% endfor -%}
{%- endif %}

{% else -%}
No significant changes.

{% endif %}
{%- endfor +%}
{#
This comment adds one more newline at the end of the rendered newsfile content.
In this way the there are 2 newlines between the latest release and the previous release content.
#}

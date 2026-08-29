<!-- Default-stijl voor de laag `vlakken` (issue #67, uitgebreid in #98 en #104): alles wat
     bij de uitslag van deze run hoort en geen punt of lijn is, in één laag. Rule-based op
     `soort`: de drie externe soorten (pand, bouwwerk, water) met een eigen omlijning en een
     doorzichtige vulling, zodat de riolering eronder zichtbaar blijft, het gemengde
     deelstelsel van RVZ-006 (voorheen de eigen laag `gemengd_zonder_overstort`) met de
     rode vlakvulling die het daar had, en de wegvakken van EXT-009 in drie regels op de
     kolom `status`. Die laatste drie zijn de enige vlakken die ook zonder melding bestaan:
     groen betekent "gekeken, er ligt riolering", grijs "niet beoordeeld" (BO-79). De kleur
     volgt `status` en is dezelfde als in de objectlagen. `styleCategories` noemt MapTips,
     anders leest QGIS het mapTip-element niet terug uit layer_styles. -->
<qgis version="3.28" styleCategories="Symbology|MapTips">
  <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">
    <rules key="{cc000000-0000-4000-8000-000000000000}">
      <rule filter="&quot;soort&quot; = 'pand'" symbol="0" label="Pand (BGT/BAG)" key="{cc000000-0000-4000-8000-000000000001}"/>
      <rule filter="&quot;soort&quot; = 'bouwwerk'" symbol="1" label="Overig bouwwerk (BGT)" key="{cc000000-0000-4000-8000-000000000002}"/>
      <rule filter="&quot;soort&quot; = 'water'" symbol="2" label="Waterdeel (BGT)" key="{cc000000-0000-4000-8000-000000000003}"/>
      <rule filter="&quot;soort&quot; = 'gemengd_deelstelsel'" symbol="3" label="Gemengd deelstelsel zonder overstort (RVZ-006)" key="{cc000000-0000-4000-8000-000000000004}"/>
      <rule filter="&quot;soort&quot; = 'wegvak' AND &quot;status&quot; = 'rood'" symbol="4" label="Straat zonder riolering (EXT-009)" key="{cc000000-0000-4000-8000-000000000005}"/>
      <rule filter="&quot;soort&quot; = 'wegvak' AND &quot;status&quot; = 'groen'" symbol="5" label="Straat met riolering (EXT-009)" key="{cc000000-0000-4000-8000-000000000006}"/>
      <rule filter="&quot;soort&quot; = 'wegvak' AND &quot;status&quot; = 'grijs'" symbol="6" label="Straat niet beoordeeld (EXT-009)" key="{cc000000-0000-4000-8000-000000000007}"/>
    </rules>
    <symbols>
      <symbol type="fill" name="0" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="178,24,43,0"/>
          <prop k="style" v="no"/>
          <prop k="outline_color" v="178,24,43,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="230,97,1,0"/>
          <prop k="style" v="no"/>
          <prop k="outline_color" v="230,97,1,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="33,102,172,0"/>
          <prop k="style" v="no"/>
          <prop k="outline_color" v="33,102,172,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="3" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="215,48,39,60"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="215,48,39,255"/>
          <prop k="outline_width" v="0.6"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="4" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="178,24,43,70"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="178,24,43,255"/>
          <prop k="outline_width" v="0.5"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="5" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="77,146,33,50"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="77,146,33,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
      <symbol type="fill" name="6" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="119,119,119,50"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="119,119,119,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <!-- Eén maptip voor beide soorten rijen: een deelstelsel draagt zijn popup voorgebakken
       in `popup_html` (het toont zijn meldingen, ook de systemische; zie BO-59), een extern
       vlak draagt die kolom leeg en krijgt zijn tekst hier uit de kolommen. QGIS kent maar
       één maptip per laag, dus de keuze zit in de expressie. Het stijlblok is de vereniging
       van de twee: de klassen van `objectkaart.popup_html` plus de drie van het externe
       vlak (k/l/t, r, c). -->
  <mapTip enabled="1"><![CDATA[<style>
  .gwsw-popup { font-family: sans-serif; font-size: 9pt; color: #222; }
  .gwsw-popup .k { border-bottom: 1px solid #bbb; padding-bottom: 2px; margin-bottom: 4px; }
  .gwsw-popup .l { font-weight: bold; }
  .gwsw-popup .t { color: #555; margin-left: 6px; text-transform: uppercase; font-size: 7pt; }
  .gwsw-popup .s { float: right; text-transform: uppercase; font-size: 7pt; }
  .s-rood .s { color: #b2182b; }
  .s-oranje .s { color: #e08214; }
  .s-groen .s { color: #4d9221; }
  .s-grijs .s { color: #777; }
  .gwsw-popup .f, .gwsw-popup .r { color: #555; font-size: 8pt; margin-bottom: 4px; }
  .gwsw-popup .m { margin: 0; padding-left: 14px; }
  .gwsw-popup .m li { margin-bottom: 3px; }
  .gwsw-popup .e { font-weight: bold; margin-right: 3px; }
  .e-F .e { color: #b2182b; }
  .e-W .e { color: #e08214; }
  .gwsw-popup .c { font-weight: bold; margin-right: 4px; }
  .gwsw-popup .v, .gwsw-popup .d, .gwsw-popup .h {
    color: #666; font-size: 8pt; margin-left: 5px;
  }
  .gwsw-popup .x, .gwsw-popup .z, .gwsw-popup .n {
    color: #666; font-size: 8pt; margin-top: 4px;
  }
</style>
<div style="width:300px">[% CASE WHEN coalesce("popup_html", '') <> '' THEN "popup_html" ELSE
  '<div class="gwsw-popup"><div class="k"><span class="l">' || coalesce("label", '') || '</span><span class="t">' || coalesce("soort", '') || '</span></div>'
  || '<div class="r">' || coalesce("subtype", '')
  || CASE WHEN coalesce("relatie", '') <> '' THEN ' &middot; ' || "relatie" ELSE '' END
  || CASE WHEN "afstand_min_m" IS NOT NULL THEN ' &middot; ' || format_number("afstand_min_m", 2) || ' m' ELSE '' END
  || '</div><div class="c">' || to_string(coalesce("aantal_meldingen", 0)) || ' melding(en) &middot; ' || coalesce("check_ids", '') || '<br/>' || coalesce("bronbestand", '') || '</div></div>'
END %]</div>]]></mapTip>
  <legend type="default-vector"/>
</qgis>

<!-- Default-stijl voor de laag `vlakken` (issue #67): de externe vlakken waar een
     EXT-melding naar wijst, in één laag. Rule-based op `soort` met drie regels (pand,
     bouwwerk, water); elk een eigen omlijning en een doorzichtige vulling, zodat de
     riolering eronder zichtbaar blijft. De laag volgt de testuitkomst: elk vlak hier is
     door ten minste één melding aangewezen. `styleCategories` noemt MapTips, anders leest
     QGIS het mapTip-element niet terug uit layer_styles. -->
<qgis version="3.28" styleCategories="Symbology|MapTips">
  <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">
    <rules key="{cc000000-0000-4000-8000-000000000000}">
      <rule filter="&quot;soort&quot; = 'pand'" symbol="0" label="Pand (BGT/BAG)" key="{cc000000-0000-4000-8000-000000000001}"/>
      <rule filter="&quot;soort&quot; = 'bouwwerk'" symbol="1" label="Overig bouwwerk (BGT)" key="{cc000000-0000-4000-8000-000000000002}"/>
      <rule filter="&quot;soort&quot; = 'water'" symbol="2" label="Waterdeel (BGT)" key="{cc000000-0000-4000-8000-000000000003}"/>
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
    </symbols>
  </renderer-v2>
  <mapTip enabled="1"><![CDATA[<style>
  .gwsw-popup { font-family: sans-serif; font-size: 9pt; color: #222; }
  .gwsw-popup .k { border-bottom: 1px solid #bbb; padding-bottom: 2px; margin-bottom: 4px; }
  .gwsw-popup .l { font-weight: bold; }
  .gwsw-popup .t { color: #555; margin-left: 6px; text-transform: uppercase; font-size: 7pt; }
  .gwsw-popup .r { color: #555; font-size: 8pt; margin-bottom: 4px; }
  .gwsw-popup .c { color: #666; font-size: 8pt; margin-top: 4px; }
</style>
<div class="gwsw-popup" style="width:280px">
  <div class="k"><span class="l">[% "label" %]</span><span class="t">[% "soort" %]</span></div>
  <div class="r">[% coalesce("subtype", '') %][% CASE WHEN "relatie" IS NOT NULL AND "relatie" <> '' THEN ' &middot; ' || "relatie" ELSE '' END %][% CASE WHEN "afstand_min_m" IS NOT NULL THEN ' &middot; ' || format_number("afstand_min_m", 2) || ' m' ELSE '' END %]</div>
  <div class="c">[% "aantal_meldingen" %] melding(en) &middot; [% "check_ids" %]<br/>[% "bronbestand" %]</div>
</div>]]></mapTip>
  <legend type="default-vector"/>
</qgis>

<!-- Default-stijl voor de laag `gemengd_zonder_overstort` (issue #75): de gemengde
     deelstelsels waarop RVZ-006 aansloeg, als vlak om hun strengen. Eén vlaksymbool en
     geen regels: elke rij in deze laag is een gebrek, dus er valt niets te filteren.
     De vervallen stelsellaag bevatte ook de goede stelsels en had die filter wel nodig.
     `styleCategories` noemt MapTips, anders leest QGIS het mapTip-element niet terug
     uit layer_styles. -->
<qgis version="3.28" styleCategories="Symbology|MapTips">
  <renderer-v2 type="singleSymbol" forceraster="0" symbollevels="0">
    <symbols>
      <symbol type="fill" name="0" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="215,48,39,60"/>
          <prop k="style" v="solid"/>
          <prop k="outline_color" v="215,48,39,255"/>
          <prop k="outline_width" v="0.6"/>
          <prop k="outline_style" v="solid"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <mapTip enabled="1"><![CDATA[<style>
  .gwsw-popup { font-family: sans-serif; font-size: 9pt; color: #222; }
  .gwsw-popup .k { border-bottom: 1px solid #bbb; padding-bottom: 2px; margin-bottom: 4px; }
  .gwsw-popup .l { font-weight: bold; }
  .gwsw-popup .t { color: #555; margin-left: 6px; }
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
<div style="width:300px">[% "popup_html" %]</div>]]></mapTip>
  <legend type="default-vector"/>
</qgis>

<!-- Default-stijl voor de naloopwerklaag. Het filter laat systemische meldingen
     weg: drie meldingtypen die op vrijwel elke put aanslaan zouden anders het hele
     kaartbeeld rood kleuren. Ze staan wel in het bestand; zet het filter uit om ze
     te zien. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="ernst" forceraster="0" symbollevels="0">
    <categories>
      <category value="F" symbol="0" label="Fout" render="true"/>
      <category value="W" symbol="1" label="Waarschuwing" render="true"/>
    </categories>
    <symbols>
      <symbol type="marker" name="0" alpha="1">
        <layer class="SimpleMarker">
          <prop k="name" v="cross_fill"/>
          <prop k="color" v="203,24,29,255"/>
          <prop k="outline_color" v="255,255,255,255"/>
          <prop k="size" v="3.4"/>
        </layer>
      </symbol>
      <symbol type="marker" name="1" alpha="1">
        <layer class="SimpleMarker">
          <prop k="name" v="triangle"/>
          <prop k="color" v="230,145,56,255"/>
          <prop k="outline_color" v="255,255,255,255"/>
          <prop k="size" v="3"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

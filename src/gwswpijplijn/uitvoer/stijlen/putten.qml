<!-- Default-stijl voor de laag `putten`: kleur naar de zwaarste melding op het
     object, grootte naar het aantal meldingen. Systemische meldingen tellen niet
     mee in n_fout en n_waarschuwing, zodat het kaartbeeld onderscheidend blijft. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="ergste_ernst" forceraster="0" symbollevels="0">
    <categories>
      <category value="F" symbol="0" label="Fout" render="true"/>
      <category value="W" symbol="1" label="Waarschuwing" render="true"/>
      <category value="geen" symbol="2" label="Geen melding" render="true"/>
    </categories>
    <symbols>
      <symbol type="marker" name="0" alpha="1">
        <layer class="SimpleMarker">
          <prop k="name" v="circle"/>
          <prop k="color" v="203,24,29,255"/>
          <prop k="outline_color" v="60,60,60,255"/>
          <prop k="size" v="3"/>
        </layer>
      </symbol>
      <symbol type="marker" name="1" alpha="1">
        <layer class="SimpleMarker">
          <prop k="name" v="circle"/>
          <prop k="color" v="230,145,56,255"/>
          <prop k="outline_color" v="60,60,60,255"/>
          <prop k="size" v="2.6"/>
        </layer>
      </symbol>
      <symbol type="marker" name="2" alpha="1">
        <layer class="SimpleMarker">
          <prop k="name" v="circle"/>
          <prop k="color" v="180,180,180,140"/>
          <prop k="outline_color" v="140,140,140,255"/>
          <prop k="size" v="1.6"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

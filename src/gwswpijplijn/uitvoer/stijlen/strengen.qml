<!-- Default-stijl voor de laag `strengen`: zelfde kleurcodering als de putten. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="ergste_ernst" forceraster="0" symbollevels="0">
    <categories>
      <category value="F" symbol="0" label="Fout" render="true"/>
      <category value="W" symbol="1" label="Waarschuwing" render="true"/>
      <category value="geen" symbol="2" label="Geen melding" render="true"/>
    </categories>
    <symbols>
      <symbol type="line" name="0" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="203,24,29,255"/>
          <prop k="line_width" v="0.9"/>
        </layer>
      </symbol>
      <symbol type="line" name="1" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="230,145,56,255"/>
          <prop k="line_width" v="0.7"/>
        </layer>
      </symbol>
      <symbol type="line" name="2" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="150,150,150,160"/>
          <prop k="line_width" v="0.3"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

<!-- Default-stijl voor de laag `strengen`.

     De lijnkleur volgt de zwaarste melding op het object. Daar bovenop tekenen drie
     regels de richting: een groene pijl als het BOB-verval met de getekende lijn
     meeloopt, twee tegengestelde pijlen als lijn en verval elkaar tegenspreken (blauw
     is de tekenrichting, rood het verval), en een grijze pijl als er geen BOB-verval
     te bepalen valt. Een regelgebaseerde renderer tekent alle regels die passen, dus
     kleur en pijl komen over elkaar heen. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">
    <rules key="{aa000000-0000-4000-8000-000000000000}">
      <rule key="{aa000000-0000-4000-8000-000000000001}" filter="&quot;ergste_ernst&quot; = 'F'" symbol="0" label="Fout"/>
      <rule key="{aa000000-0000-4000-8000-000000000002}" filter="&quot;ergste_ernst&quot; = 'W'" symbol="1" label="Waarschuwing"/>
      <rule key="{aa000000-0000-4000-8000-000000000003}" filter="&quot;ergste_ernst&quot; = 'geen'" symbol="2" label="Geen melding"/>
      <rule key="{aa000000-0000-4000-8000-000000000004}" filter="&quot;richting_bob&quot; = 'mee'" symbol="3" label="BOB volgt de lijnrichting"/>
      <rule key="{aa000000-0000-4000-8000-000000000005}" filter="&quot;richting_bob&quot; = 'tegen'" symbol="4" label="BOB tegen de lijnrichting in"/>
      <rule key="{aa000000-0000-4000-8000-000000000006}" filter="&quot;richting_bob&quot; = 'onbekend'" symbol="5" label="BOB-richting niet te bepalen"/>
    </rules>
    <symbols>
      <symbol type="line" name="0" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="203,24,29,255"/><prop k="line_width" v="0.9"/></layer></symbol>
      <symbol type="line" name="1" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="230,145,56,255"/><prop k="line_width" v="0.7"/></layer></symbol>
      <symbol type="line" name="2" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="150,150,150,160"/><prop k="line_width" v="0.3"/></layer></symbol>
      <symbol type="line" name="3" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <symbol type="marker" name="@3@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="27,120,55,255"/>
              <prop k="outline_color" v="27,120,55,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol type="line" name="4" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <prop k="offset" v="1.2"/>
          <symbol type="marker" name="@4@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="33,102,172,255"/>
              <prop k="outline_color" v="33,102,172,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <prop k="offset" v="-1.2"/>
          <symbol type="marker" name="@4@1" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="178,24,43,255"/>
              <prop k="outline_color" v="178,24,43,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="180"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol type="line" name="5" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <symbol type="marker" name="@5@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="130,130,130,255"/>
              <prop k="outline_color" v="130,130,130,255"/>
              <prop k="size" v="2.6"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

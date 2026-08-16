<!-- Default-stijl voor de naloopwerklaag.

     De regels filteren op `systemisch = 0`. Een meldingtype dat op vrijwel elke put
     aanslaat zegt iets over de export als geheel; even zwaar getekend als een los
     gebrek kleurt het het hele kaartbeeld. Die meldingen blijven volledig in het
     bestand staan (in `meldingen` en in `meldinglocaties`), maar de standaardstijl
     laat ze weg. Wie ze wil zien, verwijdert het filter uit de regel of opent de
     `meldingen`-tabel.

     Een regelgebaseerde renderer is hier bewust gekozen boven een gecategoriseerde:
     een laagfilter (subset string) reist niet mee in een QML, een regelfilter wel. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">
    <rules key="{4b9a1e3c-0000-4000-8000-000000000001}">
      <rule key="{4b9a1e3c-0000-4000-8000-000000000002}"
            filter="&quot;systemisch&quot; = 0 AND &quot;ernst&quot; = 'F'"
            symbol="0" label="Fout"/>
      <rule key="{4b9a1e3c-0000-4000-8000-000000000003}"
            filter="&quot;systemisch&quot; = 0 AND &quot;ernst&quot; = 'W'"
            symbol="1" label="Waarschuwing"/>
    </rules>
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

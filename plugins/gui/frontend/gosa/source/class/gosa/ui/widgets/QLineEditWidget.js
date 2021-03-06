/*========================================================================

   This file is part of the GOsa project -  http://gosa-project.org

   Copyright:
      (C) 2010-2012 GONICUS GmbH, Germany, http://www.gonicus.de

   License:
      LGPL-2.1: http://www.gnu.org/licenses/lgpl-2.1.html

   See the LICENSE file in the project's top-level directory for details.

======================================================================== */

qx.Class.define("gosa.ui.widgets.QLineEditWidget", {

  extend: gosa.ui.widgets.MultiEditWidget,

  construct: function(){
    this.base(arguments);
  },

  properties: {

    /* Tells the widget how to display its contents
     * e.g. for mode 'password' show [***   ] only.
     * */
    echoMode : {
      init : "normal",
      check : ["normal", "password"],
      apply : "_setEchoMode",
      nullable: true
    }
  },

  statics: {

    /* Create a readonly representation of this widget for the given value.
     * This is used while merging object properties.
     * */
    getMergeWidget: function(value){
      var container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      for(var i=0;i<value.getLength(); i++){
        var w = new qx.ui.form.TextField(value.getItem(i));
        w.setReadOnly(true);
        container.add(w);
      }
      return(container);
    }
  },


  members: {
    _default_value: "",

    /* Set a new value for the widget given by id.
     * */
    _setWidgetValue: function(id, value){
      try{
        this._getWidget(id).setValue(value);
      }catch(e){
        this.error("failed to set widget value for " + this.getAttribute() + ". "+ e);
      }
    },

    _setEchoMode: function(){
      this._current_length = 0;
      this.removeAll();
      this._widgetContainer = [];
      this._generateGui();
    },

    shortcutExecute : function()
    {
      this.focus();
    },

    /* Creates an input-widget depending on the echo mode (normal/password)
     * and connects the update listeners
     * */
    _createWidget: function(){
      var w;

      if(this.getEchoMode() == "password"){
        w = new qx.ui.form.PasswordField();
      }else{
        w = new qx.ui.form.TextField();
        w.getContentElement().setAttribute("spellcheck", true);
      }
      if(this.getPlaceholder()){
        w.setPlaceholder(this.getPlaceholder());
      }

      if(this.getMaxLength()){
        w.setMaxLength(this.getMaxLength());
      }

      w.setLiveUpdate(true);
      w.addListener("focusout", this._propertyUpdater, this);
      w.addListener("changeValue", this._propertyUpdaterTimed, this);

      return(w);
    }
  }
});

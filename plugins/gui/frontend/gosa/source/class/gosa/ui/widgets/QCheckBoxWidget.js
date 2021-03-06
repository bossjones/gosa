/*========================================================================

   This file is part of the GOsa project -  http://gosa-project.org
  
   Copyright:
      (C) 2010-2012 GONICUS GmbH, Germany, http://www.gonicus.de
  
   License:
      LGPL-2.1: http://www.gnu.org/licenses/lgpl-2.1.html
  
   See the LICENSE file in the project's top-level directory for details.

======================================================================== */

qx.Class.define("gosa.ui.widgets.QCheckBoxWidget", {

  extend: gosa.ui.widgets.Widget,

  construct: function(){
    this.base(arguments);  
    this.contents.setLayout(new qx.ui.layout.VBox(5));

    this._chkBoxWidget = new qx.ui.form.CheckBox();
    this.contents.add(this._chkBoxWidget);

    /* Once the widget gets visible add a listener which 
     * acts on the value modifications.
     *
     * This is required to let the GroupBox work. It shows/hides
     * its values depending on checkbox values.
     * */
    this._chkBoxWidget.addListener("appear", function(){
        this._chkBoxWidget.addListener("changeValue", function(){
          this.getValue().removeAll();
          this.getValue().push(this._chkBoxWidget.getValue());
          this.fireDataEvent("changeValue", this.getValue().copy());
        }, this);
      }, this);

    // Bind valid/invalid messages
    this.bind("valid", this._chkBoxWidget, "valid");
    this.bind("invalidMessage", this._chkBoxWidget, "invalidMessage");
  },

  properties: {

    // The checkbox label-txt
    label : {
      init : "",
      check : "String",
      event : "_labelChanged",
      apply : "_applyLabel"
    }
  },

  destruct : function(){
    this._disposeObjects("_chkBoxWidget");

    // Remove all listeners and then set our values to null.
    qx.event.Registration.removeAllListeners(this); 

    this.setBuddyOf(null);
    this.setGuiProperties(null);
    this.setValues(null);
    this.setValue(null);
    this.setBlockedBy(null);
  },

  statics: { 
 
    /* Create a readonly representation of this widget for the given value. 
     * This is used while merging object properties. 
     * */ 
    getMergeWidget: function(value){ 
      var w = new qx.ui.form.TextField(); 
      w.setReadOnly(true); 
      if(value.getLength()){
        w.setValue(value.getItem(0) + "");
      }
      return(w);
    }
  },

  members: {

    _chkBoxWidget: null,

    /* Returns the widget values in a clean way,
     * to avoid saving null or empty values for an object
     * property.
     * */
    getCleanValues: function()
    {
      return(new qx.data.Array([this._chkBoxWidget.getValue()]));
    },

    /* Apply the tabstop index
     * */
    _applyTabStopIndex: function(index){
      this._chkBoxWidget.setTabIndex(index);
    },

    _applyLabel : function(value, old_value) {
      this._chkBoxWidget.setLabel(this['tr'](value));
    },

    /* Apply method for the value property.
     * This method will regenerate the gui.
     * */
    _applyValue: function(value, old_value){

      // This happens when this widgets gets destroyed - all properties will be set to null.
      if(value === null){
        return;
      }

      if(value && value.length){
        this._chkBoxWidget.setValue(value.getItem(0) == true);
      }
    },

    _applyGuiProperties: function(props){

      // This happens when this widgets gets destroyed - all properties will be set to null.
      if(!props){
        return;
      }

      if(props["text"] && props["text"]["string"]){
        this.setLabel(props["text"]["string"]);
      }
    },

    focus: function(){
      this._chkBoxWidget.focus();
    }
  }
});

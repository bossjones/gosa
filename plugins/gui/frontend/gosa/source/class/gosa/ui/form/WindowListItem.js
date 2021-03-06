

qx.Class.define("gosa.ui.form.WindowListItem", {
  extend: qx.ui.form.ListItem,

  /*
  *****************************************************************************
     PROPERTIES
  *****************************************************************************
  */
  properties : {
    appearance :
    {
      refine : true,
      init : "gosa-listitem-window"
    },

    window: {
      check: "qx.ui.window.Window",
      nullable: true
    },

    object: {
      check: "Object",
      nullable: true,
      apply: "_applyObject"
    }
  },

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */
  members : {
    _applyObject: function(object) {
      if (object) {
        if (object instanceof gosa.ui.form.WorkflowItem) {
          object.bind("label", this, "label");
          object.bind("icon", this, "icon");
        } else if (!object.uuid) {
          // new object
          this.setLabel(object.baseType+"*");
          this.setIcon(gosa.util.Icons.getIconByType(object.baseType, 22));
        } else {
          // we need to break out of the property apply chain to allow promises to be used
          // otherwise we get a warning about a created but not returned promise
          new qx.util.DeferredCall(function() {
            // try to get the search result for this dn, to get the mapped title/icon values
            gosa.io.Rpc.getInstance().cA("getObjectSearchItem", object.dn)
            .then(function(result) {
              this.setLabel(result.title);
              this.setIcon(result.icon ? result.icon : gosa.util.Icons.getIconByType(result.tag, 22));
            }, this)
            .catch(function(error) {
              this.error(error);
              // fallback
              var dnPart = qx.util.StringSplit.split(qx.util.StringSplit.split(object.dn, "\,")[0], "=")[1];
              this.setLabel(dnPart);
            }, this);
          }, this).schedule();
        }
      }
    }
  }
});
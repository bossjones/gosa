/*========================================================================

   This file is part of the GOsa project -  http://gosa-project.org
  
   Copyright:
      (C) 2010-2012 GONICUS GmbH, Germany, http://www.gonicus.de
  
   License:
      LGPL-2.1: http://www.gnu.org/licenses/lgpl-2.1.html
  
   See the LICENSE file in the project's top-level directory for details.

======================================================================== */

qx.Class.define("gosa.data.model.SelectBoxItem",
{
  extend : qx.core.Object,

  properties : {
    value : {
      check : "String",
      event : "changeValue"
    },

    key : {
      event : "changeKey",
      nullable: true
    },

    icon : {
      check : "String",
      event : "changeIcon",
      nullable: true
    }
  },


  members : {
    toString: function() {
      return this.getValue();
    }
  }

});

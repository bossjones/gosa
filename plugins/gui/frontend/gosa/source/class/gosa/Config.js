/*========================================================================

   This file is part of the GOsa project -  http://gosa-project.org
  
   Copyright:
      (C) 2010-2012 GONICUS GmbH, Germany, http://www.gonicus.de
  
   License:
      LGPL-2.1: http://www.gnu.org/licenses/lgpl-2.1.html
  
   See the LICENSE file in the project's top-level directory for details.

======================================================================== */

qx.Class.define("gosa.Config", {

  type: "static",

  statics: {

    url: "/rpc",
    ws: "/ws",
    spath: "/static",
    service: "GOsa JSON-RPC service",
    actionDelimiter: '#',
    timeout: 60000,
    notifications: window.webkitNotifications || window.notifications,

    getTheme : function()
    {
      if (gosa.Config.theme) {
          return gosa.Config.theme;
      }

      return "default";
    },

    getImagePath : function(icon, size)
    {
        if (!size) {
            size = "22";
        }

        return "gosa/themes/" + gosa.Config.getTheme() + "/" + size + "/" + icon;
    }
  }
});
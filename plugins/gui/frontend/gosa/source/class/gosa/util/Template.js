qx.Class.define("gosa.util.Template", {
  type : "static",

  statics : {

    /**
     * Takes a json template as string and compiles it to a javascript object (includes translation etc.).
     *
     * @param template {String} The template as a json string
     * @return {Object} Compiled template
     */
    compileTemplate : function(template) {
      var translator = gosa.engine.Translator.getInstance();
      var translated = translator.translateJson(template);
      return JSON.parse(translated);
    },

    /**
     * Gives an array of maps with a template and other information.
     *
     * @param objectName {String} The objectName (e.g. "PosixUser")
     * @return {Array} An (maybe empty) array of hash maps
     */
    getTemplateObjects : function(objectName) {
      qx.core.Assert.assertString(objectName);

      return gosa.data.TemplateRegistry.getInstance().getTemplates(objectName).map(function(template) {
        return {
          extension : objectName,
          template : template
        };
      });
    },

    /**
     * Finds the identifying name of a dialog template.
     *
     * @param template {String} The template as a json string (i.e. unparsed)
     * @return {String | null} The name of the template or null if not found/no valid dialog template
     */
    getDialogName : function(template) {
      qx.core.Assert.assertString(template);
      var json = JSON.parse(template);
      if (json.hasOwnProperty("type") && json.type === "widget" &&
          json.hasOwnProperty("properties") && (typeof json.properties === "object") &&
          json.properties.hasOwnProperty("dialogName") && (typeof json.properties.dialogName === "string")) {
            return json.properties.dialogName;
          }
      return null;
    },

    /**
     * Find all rpc calls that are made from within the dialog.
     *
     * @param dialogName {String} The dialog/template name; parsed template will be searched automatically
     * @return {Array} An (maybe empty) array of all rpc calls found in the dialog template
     */
    getDialogRpc : function(dialogName) {
      qx.core.Assert.assertString(dialogName);
      var template = gosa.data.TemplateRegistry.getInstance().getDialogTemplate(dialogName);

      if (!template || !qx.lang.Type.isObject(template.properties) || !template.properties.dialogName) {
        return [];
      }

      var result = [];
      var rec = function(node) {
        if (!qx.lang.Type.isObject(node)) {
          return;
        }
        if (qx.lang.Type.isObject(node.extensions) && qx.lang.Type.isObject(node.extensions.guiProperties) &&
            !!node.extensions.guiProperties.callObjectMethod) {
          result.push(node.extensions.guiProperties.callObjectMethod);
        }
        if (qx.lang.Type.isArray(node.children)) {
          node.children.forEach(rec);
        }
      };

      rec(template);
      return result;
    },

    /**
     * Some templates have information hidden inside them, e.g. the category title or extension names.
     * This function extracts the information and writes them to the gosa.Cache object.
     *
     * @param name {String} Name of the extension
     */
    fillTemplateCache : function(name) {
      qx.core.Assert.assertString(name);

      gosa.data.TemplateRegistry.getInstance().getTemplates(name).forEach(function(tmpl) {

        // category title
        gosa.Cache.objectCategories[name] = name;
        if (tmpl.hasOwnProperty("type") && tmpl.type === "widget" &&
            tmpl.hasOwnProperty("properties") && (typeof tmpl.properties === "object") &&
            tmpl.properties.hasOwnProperty("categoryTitle") && (typeof tmpl.properties.categoryTitle === "string")) {
          gosa.Cache.objectCategories[name] = tmpl.properties.categoryTitle;
        }

        // extension config (translated name, icon)
        if (!gosa.Cache.extensionConfig.hasOwnProperty(name) && tmpl.extensions && tmpl.extensions.tabConfig) {
          var result = {};
          var tabConfig = tmpl.extensions.tabConfig;

          // extension title
          if (tabConfig.title) {
            result.title = tabConfig.title;
          }

          // extension icon
          if (tabConfig.icon && tmpl.extensions.resources) {
            var iconSource = tmpl.extensions.resources[tabConfig.icon];
            result.icon = gosa.engine.ResourceManager.convertResource(iconSource);
          }
          gosa.Cache.extensionConfig[name] = result;
        }
      });
    }
  }
});

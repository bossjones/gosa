qx.Interface.define("gosa.engine.extensions.IExtension", {

  members : {
    process : function(data, target, context) {
      this.assertQxObject(target);
      if (context) {
        this.assertInstance(context, gosa.engine.Context);
      }
    }
  }
});

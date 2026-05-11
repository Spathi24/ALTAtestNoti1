/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;

/**
 * Reference data instead of enum to avoid duplicated nested enums in Java.
 */
// line 87 "../../model-v0.1.ump"
public class SourceSystem
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //SourceSystem Attributes
  private String code;
  private String displayName;

  //Helper Variables
  private int cachedHashCode;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public SourceSystem(String aCode)
  {
    cachedHashCode = -1;
    code = aCode;
    displayName = null;
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setDisplayName(String aDisplayName)
  {
    boolean wasSet = false;
    displayName = aDisplayName;
    wasSet = true;
    return wasSet;
  }

  public String getCode()
  {
    return code;
  }

  public String getDisplayName()
  {
    return displayName;
  }

  public boolean equals(Object obj)
  {
    if (obj == null) { return false; }
    if (!getClass().equals(obj.getClass())) { return false; }

    SourceSystem compareTo = (SourceSystem)obj;
  
    if (getCode() == null && compareTo.getCode() != null)
    {
      return false;
    }
    else if (getCode() != null && !getCode().equals(compareTo.getCode()))
    {
      return false;
    }

    return true;
  }

  public int hashCode()
  {
    if (cachedHashCode != -1)
    {
      return cachedHashCode;
    }
    cachedHashCode = 17;
    if (getCode() != null)
    {
      cachedHashCode = cachedHashCode * 23 + getCode().hashCode();
    }
    else
    {
      cachedHashCode = cachedHashCode * 23;
    }

    
    return cachedHashCode;
  }

  public void delete()
  {}


  public String toString()
  {
    return super.toString() + "["+
            "code" + ":" + getCode()+ "," +
            "displayName" + ":" + getDisplayName()+ "]";
  }
}
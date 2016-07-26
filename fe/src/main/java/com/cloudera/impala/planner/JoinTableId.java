// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

package com.cloudera.impala.planner;

import com.cloudera.impala.common.Id;
import com.cloudera.impala.common.IdGenerator;

public class JoinTableId extends Id<JoinTableId> {
  // Construction only allowed via an IdGenerator.
  protected JoinTableId(int id) {
    super(id);
  }

  public static JoinTableId INVALID;
  static {
    INVALID = new JoinTableId(Id.INVALID_ID);
  }

  public static IdGenerator<JoinTableId> createGenerator() {
    return new IdGenerator<JoinTableId>() {
      @Override
      public JoinTableId getNextId() { return new JoinTableId(nextId_++); }
      @Override
      public JoinTableId getMaxId() { return new JoinTableId(nextId_ - 1); }
    };
  }

  @Override
  public String toString() {
    return String.format("%02d", id_);
  }
}
